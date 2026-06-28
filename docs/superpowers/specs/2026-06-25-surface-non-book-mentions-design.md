# Surface non-book mentions (places & products) — design

Date: 2026-06-25
Status: Approved, pre-implementation

## Problem

The backend already extracts and stores all three mention types — `book`,
`place`, `product` — and the `/v1/saved-sources` API returns every item with its
`category`. But the **mobile client is book-shaped end to end** and discards the
rest:

- `mobile/src/captures.ts:64` filters items to `category === 'book'` before
  anything renders.
- The client model is `Capture.books: BookMention[]`; status is `'no_books'`;
  the detail section header reads "Books mentioned"; the no-image placeholder is
  a literal book spine.

Result: a saved restaurant or product post extracts successfully, then the user
sees "No books found in this post" while the data sits invisible in the DB.

This is the **surfacing** phase only. Enrichment (place photos/addresses,
product images/links) is a deliberately separate, later phase.

## Scope

- **In scope:** mobile client changes to display book, place, and product
  mentions, generalizing the book-only model into a type-neutral one. Book is
  just one type.
- **Out of scope:** any backend / API change; enrichment of places or products;
  per-type images (none exist yet); web app (it is a landing page only, no
  saved-items UI).

## Key product facts driving the design

- **Posts are single-type.** A saved post yields books, *or* places, *or*
  products — not a blend. So the detail screen needs **one adaptive section**,
  not grouping, per-row type badges, or dominant-type logic.
- **No images for non-books yet.** Every place/product row uses a placeholder
  this phase.

## Decisions

1. **Generalize the model (Approach A).** Rename `BookMention` → `Mention` with a
   `category` field; `Capture.books` → `Capture.mentions`. Chosen over a
   minimal filter-lift (would leave a restaurant rendering as a book spine under
   a "Books mentioned" header) and over per-type card components (premature —
   rows are near-identical; only the glyph differs).
2. **Type-icon tile placeholder.** Reuse the existing colored tile, swap the
   glyph by category: map pin (place), tag (product), existing book spine +
   initials (book). The colored-tile + initials logic already works for any
   title; the glyph is the only type-specific pixel.
3. **Confidence floor unchanged for now.** Keep `MIN_VISIBLE_CONFIDENCE = 0.6`
   for all types. Places/products tend to extract lower than books, so this may
   hide legitimate items — but we will tune empirically once we see real
   extraction quality rather than guess a number blind. Mark it in code as a
   per-type tuning candidate.
4. **Type-neutral copy.** Processing and empty states cannot know the post's
   intended type, so their copy enumerates all three types.

## Design

### 1. Data model & transform — `mobile/src/captures.ts`

```ts
export type MentionCategory = 'book' | 'place' | 'product';

export type Mention = {
  id: string;
  category: MentionCategory;
  title: string;
  subtitle: string | null;   // author for books; null for place/product for now
  coverImageUrl: string | null;
  initials: string;
  color: string;
};
```

- `Capture.books: BookMention[]` → `Capture.mentions: Mention[]`.
- Drop the old `synopsis` field: it was always set to `null` and never
  populated. Removing it rather than carrying dead state forward.
- `CaptureStatus` value `'no_books'` → `'no_mentions'`.
- `visibleBookItems` → `visibleMentions`: **remove** the `category === 'book'`
  filter; keep the confidence floor and the non-empty-title filter; keep the
  `position` sort; map `category` through and set `subtitle` from `author`.
- `statusFor` and `captureFromSavedSource` (and `mergeSavedSourcesWithCaptures`)
  updated to read `mentions` instead of `books`.
- No change to API types (`SourceItemInSavedSource` already carries `category`,
  `confidence`, `cover_image_url`).

### 2. Presentation mapping & card — `mobile/src/components/books.tsx` → `mentions.tsx`

A pure helper isolates all type-specific UI:

```ts
const CATEGORY_PRESENTATION: Record<MentionCategory, {
  sectionTitle: string;     // "Books mentioned" | "Places mentioned" | "Products mentioned"
  Icon: ...;                // BookSpine (existing) | PlaceIcon | ProductIcon
}>
```

- Section title derives from `mentions[0].category` (single-type posts → one
  header, no grouping).
- `MentionRow` (generalized `BookRow`): if `coverImageUrl` present → image
  (books today, place photos later with no change); else colored tile with the
  category's glyph. Title always; `subtitle` when present.
- Component renames: `BooksMentioned` → `MentionsList`,
  `ProcessingBooks` → `ProcessingMentions`, `NoBooks` → `NoMentions`;
  `FailedState` unchanged. File renamed `books.tsx` → `mentions.tsx`.

### 3. Icons — `mobile/src/components/icons.tsx`

Add `PlaceIcon` (Lucide `MapPin`) and `ProductIcon` (Lucide `Tag`), following
the existing `iconProps` wrapper pattern.

### 4. Screen wiring & copy

`mobile/src/screens/reel-detail-screen.tsx`:
- Import from `@/components/mentions`.
- Status branches (lines 54–93): `'ready'` → `<MentionsList mentions={capture.mentions} />`;
  `'processing'` → `<ProcessingMentions />`; `'no_books'` → `'no_mentions'` →
  `<NoMentions ... />`.
- `ProcessingMentions` copy is type-neutral: "Finding mentions..." /
  "Mentioned is checking this post for books, places, and products."
- Empty state: title "Nothing found in this post"; body "The post is still
  saved. Mentioned didn't find a clear book, place, or product to show here."
  `wasSkipped` variant similarly neutral.

`mobile/src/screens/home-screen.tsx`:
- Subtitle (line 60), pending-source title/button copy (lines 66, 73) → type
  neutral ("...find the books, places, and products inside.", "Ready to
  extract", etc.).

`mobile/src/components/reel-tile.tsx`: no logic change — it reads only
`status`, no book counts. The `'no_books'` → `'no_mentions'` rename flows
through its `Capture['status']` type.

## Testing & validation

- **Unit (`captures.ts` transform):** `visibleMentions` now returns
  place/product items; single-type posts produce the right `mentions` array; a
  place at 0.7 surfaces while an item at 0.5 stays hidden by the 0.6 floor;
  `statusFor` returns `'ready'` when non-book mentions exist and `'no_mentions'`
  only when empty; `subtitle` maps from `author` for books and stays `null` for
  place/product. Follow the existing `mobile/` test setup; add a transform test
  if none exists.
- **Types/lint:** `npm run typecheck` from `mobile/` — the rename surfaces every
  missed reference.
- **Manual UI:** cannot run Expo in this environment. Verification here is
  typecheck + unit tests; the on-device check (save a real restaurant/product
  post, confirm correct icon tile + header) is the user's to perform. Will not
  claim the UI works without it being seen.

## Follow-ups (later phases)

- Enrich places (address, photo, map) and products (image, link) so non-book
  cards reach book-level richness.
- Revisit `MIN_VISIBLE_CONFIDENCE` per type using real place/product data.
