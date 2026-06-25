# Enrich place mentions (address + map) — design

Date: 2026-06-25
Status: Approved, pre-implementation

## Problem

The surfacing phase (`docs/superpowers/specs/2026-06-25-surface-non-book-mentions-design.md`,
shipped on `v2-improvements`) made the mobile client type-neutral: books, places, and
products now render side by side. But only **books** are enriched. Gemini extracts a place
as nothing more than `title` + `category` + `confidence` (`src/extraction/gemini.py:16-47`),
there is no enrichment trigger for non-books (`src/ingestion/source_processor.py:64-85` only
branches on `category == "book"`), and `source_items` has no columns for an address, coords,
or a provider id. So a saved restaurant renders as a map-pin tile showing only its name —
nothing to actually revisit.

This is the **place enrichment** phase. Places were chosen first (over products) because they
have the strongest revisit value — you physically go back to a place — and a clean external
API exists (Google Places). Product enrichment is a deliberately separate, later phase.

## Scope

- **In scope:** backend place enrichment (Google Places lookup, new `places` table, additive
  `source_items` columns, enrichment trigger), additive API response fields, and mobile
  rendering of the enriched place card (address subtitle + tap-to-open Google Maps).
- **Out of scope:** product enrichment; place photos, ratings, hours, or price level;
  in-app embedded maps; any change to the frozen `/v1` HTTP contract semantics; the legacy
  `Mention` table / `src/mentions/*` path.

## Key facts driving the design

- **Books are the enrichment template.** `enrich_extracted_book_mention`
  (`src/books/enrichment.py:33-56`) resolves an external provider, upserts a typed row
  (`upsert_google_book`, `src/books/service.py:22-68`), then **denormalizes** display fields
  back onto the flat item (`src/ingestion/source_processor.py:80-85`). Places mirror this
  shape exactly — one enrichment pattern across types keeps the codebase AI-navigable.
- **Fail-open is the house style.** `find_google_book_sync`
  (`src/books/enrichment.py:25-30`) wraps the async provider in `asyncio.run` + a broad
  `except` returning `None`; a provider error silently degrades to "no enrichment." The
  relevance gate (`technical.md`, 2026-06-24) does the same: act only on a confident verdict,
  otherwise proceed safely. Place enrichment adopts both.
- **Enrichment lives on the canonical shared source cache.** Per `technical.md`
  (2026-06-21 "Shared Source Cache", 2026-06-22 "Minimal Saved Source Cache Model"),
  enriched data belongs on `sources`/`source_items` (deduped, owner-less), never per-user.
  Places dedup by Google's stable `place_id`, exactly as books dedup by
  `(provider, provider_volume_id)`.
- **Additive changes only.** New API fields and DB columns are additive/nullable. The frozen
  v1 app ignores unknown JSON keys (the mechanism that let `skip_reason` ship additively),
  so the backend can populate places without a v1 contract break.

## Decisions

1. **Places first** (over products). Strongest revisit value; clean provider API.
2. **Google Places API (New) Text Search** as the provider. Mirrors the Google Books pattern.
3. **Address + map pin only** — no photo, rating, hours, or price. This is both a product
   choice (minimal first card) and the **cost lever**: the requested field mask determines the
   billing SKU (see "Cost" below).
4. **Dedicated `places` table + FK**, deduped by Google `place_id`, with denormalized
   address/coords on `source_items` for the read path. Chosen over loose columns or a JSON
   blob to stay consistent with the typed `books` table.
5. **Gemini `location_hint`** to disambiguate matching. One optional extraction field biases
   the Places query; never persisted on its own.
6. **High-confidence matches only; otherwise fail open.** A vague name with no hint that
   returns multiple candidates is left as a bare title (today's icon-tile card) rather than
   risking a confidently-wrong address. Dropping unmatched places is explicitly rejected — it
   would hide real mentions.
7. **Enrichment runs inline in the worker**, right after extraction, in the existing
   synchronous path — same as books. An async enrichment queue and enrich-on-read were both
   rejected as premature for one cheap call at 10–15 users (YAGNI; the latter also breaks the
   canonical-cache model).
8. **Mobile place row deep-links to Google Maps** (no in-app map dependency this phase).
9. **Mobile included in this spec** (backend + client end to end), since the visible payoff
   needs a new app build regardless.

## Design

### 1. Data model & storage

New `places` table (mirrors `books`):

```
places
  id                  UUID  pk
  provider            text   ("google_places")
  provider_place_id   text   (Google standalone place id)
  name                text
  formatted_address   text
  latitude            float
  longitude           float
  maps_url            text
  raw_provider_payload json
  created_at          datetime
  updated_at          datetime
  UNIQUE(provider, provider_place_id)
```

New additive columns on `source_items` (denormalized for display, mirroring how
`book_id`/`cover_image_url` already sit on the row):

```
place_id           UUID  fk -> places.id   (null unless category == 'place' and matched)
formatted_address  text                    (null otherwise)
latitude           float                   (null otherwise)
longitude          float                   (null otherwise)
```

- **Migration:** one Alembic revision adding the `places` table and the four `source_items`
  columns. All additive/nullable — a safe expand migration, no v1 break.
- **`Mention` table untouched.** It is frozen v1 contract surface; the active path is
  `source_items`. Books still write `Mention` only because the existing enrichment signature
  takes one. Place enrichment operates directly on `SourceItem`, no `Mention` write — keeping
  the new code entirely off the frozen contract.

### 2. Extraction schema & Gemini prompt

`ExtractedMention` (`src/extraction/schemas.py:6-11`) gains one optional field:

```python
@dataclass
class ExtractedMention:
    title: str
    author: str | None = None
    category: str = "book"
    confidence: float = 0.5
    location_hint: str | None = None   # neighborhood/city/region; places only
```

- `location_hint` is populated only for places, stays `None` otherwise. It is **transient** —
  consumed by the Places lookup, then discarded. The resolved `formatted_address` is what we
  persist.
- **Prompt** (`src/extraction/gemini.py:16-27`): add a rule — *"For places: include a
  `location_hint` with any city, neighborhood, region, or country mentioned or shown (caption,
  audio, on-screen text). Omit if none is evident — do not guess."* The "do not guess"
  instruction is load-bearing: a hallucinated city confidently mismatches the lookup, which is
  worse than no hint. This mirrors the relevance gate's caption-as-untrusted-input discipline.
- **Schema** (`MENTION_SCHEMA`, `gemini.py:29-47`): add
  `"location_hint": {"type": "string"}` as an **optional** property (not in `required`).
  Existing book/product extraction is unaffected.
- **Parsing** (`src/extraction/pipeline.py:78-90`): read `location_hint` through into
  `ExtractedMention`.

### 3. Google Places provider — `src/extraction/google_places.py`

New module modeled on `src/extraction/google_books.py`.

```python
async def find_google_place(name: str, location_hint: str | None) -> GooglePlace | None
```

- **Endpoint:** `POST https://places.googleapis.com/v1/places:searchText`
- **Headers:** `X-Goog-Api-Key: <key>`, `Content-Type: application/json`,
  `X-Goog-FieldMask: places.id,places.displayName,places.formattedAddress,places.location`
- **Body:** `{"textQuery": "<name> <location_hint>"}` (hint appended when present, else just
  `name`).
- **Response mapping** → `GooglePlace` dataclass:
  - `provider_place_id` ← `places[].id` (the standalone place id)
  - `name` ← `places[].displayName.text`
  - `formatted_address` ← `places[].formattedAddress`
  - `latitude`/`longitude` ← `places[].location.{latitude,longitude}`
  - `maps_url` ← built deterministically as
    `https://www.google.com/maps/place/?q=place_id:<provider_place_id>` (no extra API call)
  - `raw_provider_payload` ← the full place object (parity with books)
- **High-confidence bar.** Save a match only when there is a top result **and**
  (a location hint was present **or** the query returned exactly one candidate). A vague,
  hintless, multi-candidate result returns `None` (fail open).
- **Returns `None`** on: no results, low-confidence per the bar above, any HTTP/parse error,
  or an unset API key.
- **Sync wrapper** `find_google_place_sync` mirrors `find_google_book_sync`: `asyncio.run`
  + broad `except` → `None`.

**Config:** add `GOOGLE_PLACES_API_KEY` (sibling to the existing Google Books config). The
key lives in `.env` (never committed). If unset, the finder returns `None` and places stay
un-enriched — no crash, same graceful degradation as the relevance gate's mode flag.

### 4. Enrichment module & trigger

New `src/places/` package mirroring `src/books/`:

- `src/places/models.py` — the `Place` SQLModel (table above).
- `src/places/service.py` — `upsert_google_place(session, google_place) -> Place`, deduped by
  `(provider, provider_place_id)`. Direct analog of `upsert_google_book`.
- `src/places/enrichment.py` — `enrich_extracted_place_item(session, item, extracted, *,
  place_finder=find_google_place_sync) -> None`. Operates **directly on the `SourceItem`**
  (no `Mention`): on a confident match, upserts the `Place`, sets `item.place_id`, and
  denormalizes `formatted_address`/`latitude`/`longitude` onto the item. On `None`, leaves the
  item as its bare title (no-op).

**Trigger** (`src/ingestion/source_processor.py:64-85`): add an `elif` branch alongside the
book branch:

```python
if extracted.category == "book":
    ...                       # unchanged
elif extracted.category == "place":
    enrich_extracted_place_item(session, item, extracted, place_finder=self._place_finder)
```

`SourceIngestion.__init__` gains a `place_finder` dependency (default
`find_google_place_sync`), parallel to the existing `book_finder` — keeps enrichment
injectable for tests.

### 5. API response shape

`SourceItemResponse` (`src/sources/schemas.py:15-28`) gains four additive optional fields:

```python
place_id:          Optional[str]   = None
formatted_address: Optional[str]   = None
latitude:          Optional[float] = None
longitude:         Optional[float] = None
```

`src/sources/read_models.py:20-41` maps them straight off the denormalized `SourceItem`
columns — **no join** to `places` on the read path (display fields already live on the item,
exactly as `cover_image_url` does for books). All additive/optional → frozen v1 app ignores
them, no contract break.

### 6. Mobile rendering

The client model is already type-neutral (`Mention` with `category`, from the surfacing
phase).

- `mobile/src/captures.ts` — `Mention` type gains optional `formattedAddress`, `latitude`,
  `longitude`; the transform maps them from the API. For places, the existing `subtitle`
  field carries `formattedAddress` (books use `author`), so a place row shows its address
  under the name with no new layout.
- `mobile/src/components/mentions.tsx` — a place row with coords becomes tappable, deep-linking
  to `maps_url` (fallback `https://maps.google.com/?q=<lat>,<lng>`). Place keeps the map-pin
  icon tile (no photo this phase). Headers ("Places mentioned"), icons, and the
  `MIN_VISIBLE_CONFIDENCE = 0.6` floor are unchanged from surfacing.
- This requires a **new app build** to render the fields, but the change is purely additive and
  off the frozen v1 path.

## Cost

The Places API (New) bills per **SKU**, triggered by the requested field mask, and bills at
the **highest** SKU among requested fields. `places.id` alone is the cheap *Text Search
Essentials (IDs Only)* SKU, but `formattedAddress`, `displayName`, and `location` are all
*Text Search Pro*. There is no way to get a usable address + map pin below Pro — so this
phase is unavoidably **Pro tier** (accepted). The field mask is deliberately minimal: adding
`places.rating`, `places.regularOpeningHours`, etc. would push the call to the pricier
Atmosphere/Enterprise SKUs. **Do not widen the field mask without re-pricing.** This serves
the `technical.md` cost-control constraint (track/limit provider cost per extraction).

## Testing & validation

- **Provider (`google_places.py`):** unit-test response parsing (id/displayName/
  formattedAddress/location → `GooglePlace`, `maps_url` construction) and the high-confidence
  bar (hint present → save; hintless single result → save; hintless multi-candidate → `None`;
  empty/error → `None`). Mock the HTTP call; do not hit the live API in tests.
- **Enrichment (`places/enrichment.py`):** with a fake `place_finder`, assert a confident
  match upserts a `Place`, sets `item.place_id`, and denormalizes address/coords; a `None`
  finder leaves the item as a bare title. Mirror the book enrichment test setup.
- **Trigger (`source_processor.py`):** a place item routes through place enrichment, a book
  item still routes through book enrichment, a product item is untouched.
- **Dedup (`places/service.py`):** two source items resolving to the same `place_id` reuse one
  `places` row.
- **API:** `SourceItemResponse` serializes the new fields for an enriched place and leaves them
  `null` for books/products/unmatched places; v1 contract regression (existing book fields
  unchanged).
- **Mobile:** `npm run typecheck` from `mobile/`; extend the existing `captures.ts` transform
  test (`npm run test:captures`) to assert place fields map through and a bare place still
  renders. On-device check (save a real restaurant post, confirm address subtitle + Maps
  deep-link, books unchanged) is the user's — Expo can't run in this environment.

## Follow-ups (later phases)

- Product enrichment (image, brand, link) — separate spec; the `places` package is the
  template.
- Revisit `MIN_VISIBLE_CONFIDENCE` per type once real place extraction-quality data exists.
- Per-extraction provider cost/latency instrumentation (the broader Axis A cost-control track).
- Richer place cards (photo/rating/hours) only if revisit data justifies the higher SKU.
