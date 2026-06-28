# Surface Non-Book Mentions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Display place and product mentions (not just books) in the Mentioned mobile app by generalizing the book-shaped client model into a type-neutral `Mention` model.

**Architecture:** Pure client-side change. The `/v1/saved-sources` API already returns every extracted item with its `category` (`book` | `place` | `product`); the mobile client currently filters to books only and is book-shaped end to end. We rename `BookMention` → `Mention` (carrying `category` + `subtitle`), drop the `category === 'book'` filter, and add a per-category presentation map that swaps the placeholder glyph (book spine / map pin / tag) and section header. No backend, API, or enrichment changes.

**Tech Stack:** TypeScript, React Native (Expo), `lucide-react-native` icons. Tests are standalone `tsx` assertion scripts run via npm scripts (no Jest in this project).

## Global Constraints

- **No backend / API / API-type changes.** `SourceItemInSavedSource` (`mobile/src/api.ts:88`) already carries `category: string`, `confidence`, `cover_image_url`. Do not modify it.
- **Posts are single-type** — a post yields books OR places OR products, never mixed. One adaptive section, no grouping, no per-row type badges.
- **Confidence floor stays `MIN_VISIBLE_CONFIDENCE = 0.6` for ALL types** this phase. Do not lower it per type; mark it in code as a per-type tuning candidate.
- **`category` from the API is a plain `string`** and must be narrowed to the `MentionCategory` union in the transform. Items whose category is not one of `book`/`place`/`product` are dropped (defensive — should not occur).
- **No enrichment, no place/product images** this phase. Non-book rows always use the icon-tile placeholder.
- **Copy is type-neutral** in processing and empty states (cannot know intended type).
- Run all commands from `mobile/`.

---

## File Structure

- `mobile/src/captures.ts` (modify) — `Mention` model + `visibleMentions` transform + status. The riskiest logic; fully unit-tested.
- `mobile/src/components/icons.tsx` (modify) — add `PlaceIcon`, `ProductIcon`.
- `mobile/src/components/mentions.tsx` (rename from `books.tsx` + modify) — presentation map, `MentionsList`, `MentionRow`, `ProcessingMentions`, `NoMentions`, `FailedState`.
- `mobile/src/screens/reel-detail-screen.tsx` (modify) — import + status-branch + props rename.
- `mobile/src/screens/home-screen.tsx` (modify) — type-neutral copy.
- `mobile/scripts/test-captures.ts` (modify) — invert the books-only assertions to assert non-book surfacing.

---

## Task 1: Generalize the data model and transform in `captures.ts`

**Files:**
- Modify: `mobile/src/captures.ts`
- Test: `mobile/scripts/test-captures.ts`

**Interfaces:**
- Consumes: `SourceItemInSavedSource` (`mobile/src/api.ts:88`), `SavedSourceResponse`, `SavedSourceStatus`.
- Produces:
  - `type MentionCategory = 'book' | 'place' | 'product'`
  - `type Mention = { id: string; category: MentionCategory; title: string; subtitle: string | null; coverImageUrl: string | null; initials: string; color: string }`
  - `type CaptureStatus = 'ready' | 'processing' | 'no_mentions' | 'failed'`
  - `Capture.mentions: Mention[]` (replaces `Capture.books`)
  - All existing exported functions keep their names: `buildCapturesFromSavedSources`, `captureFromSavedSource`, `captureFromSavedSourceCreated`, `mergeSavedSourcesWithCaptures`.

- [ ] **Step 1: Update the test to assert non-book surfacing (failing test)**

In `mobile/scripts/test-captures.ts`, replace the two `no_books` literals (lines 63, 70) with `no_mentions`, and replace the `detailedBookCapture` block (lines 73-116) with the following. This inverts the old "Ignored Product" assertion — the product must now surface, and a low-confidence item must still be hidden:

```ts
const mixedCapture = captureFromSavedSource({
  ...savedSource,
  items: [
    {
      id: '55555555-5555-4555-8555-555555555555',
      book_id: null,
      title: 'Cafe Nero',
      author: null,
      category: 'place',
      confidence: 0.7,
      google_books_url: null,
      cover_image_url: null,
      position: 0,
    },
    {
      id: '77777777-7777-4777-8777-777777777777',
      book_id: '88888888-8888-4888-8888-888888888888',
      title: 'The Left Hand of Darkness',
      author: 'Ursula K. Le Guin',
      category: 'book',
      confidence: 0.99,
      google_books_url: null,
      cover_image_url: 'https://example.com/cover.jpg',
      position: 2,
    },
    {
      id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      book_id: null,
      title: 'Low Confidence Place',
      author: null,
      category: 'place',
      confidence: 0.5,
      google_books_url: null,
      cover_image_url: null,
      position: 1,
    },
  ],
});
// Place at 0.7 surfaces; book surfaces; place at 0.5 hidden by the 0.6 floor.
assert.equal(mixedCapture.status, 'ready');
assert.deepEqual(
  mixedCapture.mentions.map((mention) => mention.title),
  ['Cafe Nero', 'The Left Hand of Darkness'],
);
assert.deepEqual(
  mixedCapture.mentions.map((mention) => mention.category),
  ['place', 'book'],
);
// subtitle: author for books, null for place/product.
assert.equal(mixedCapture.mentions[0].subtitle, null);
assert.equal(mixedCapture.mentions[1].subtitle, 'Ursula K. Le Guin');
assert.equal(mixedCapture.mentions[1].coverImageUrl, 'https://example.com/cover.jpg');

const productCapture = captureFromSavedSource({
  ...savedSource,
  items: [
    {
      id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
      book_id: null,
      title: 'Oura Ring',
      author: null,
      category: 'product',
      confidence: 0.9,
      google_books_url: null,
      cover_image_url: null,
      position: 0,
    },
  ],
});
assert.equal(productCapture.status, 'ready');
assert.equal(productCapture.mentions[0].category, 'product');
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm run test:captures`
Expected: FAIL — `tsx` reports a TypeScript/runtime error such as `Property 'mentions' does not exist` or an AssertionError on `status` (`no_books` still returned). This confirms the test exercises the new behavior before implementation.

- [ ] **Step 3: Rewrite the model and transform in `captures.ts`**

Replace lines 1-13 (the imports through the `BookMention` type) with:

```ts
import type { SavedSourceResponse, SavedSourceStatus, SourceItemInSavedSource } from './api';

export type CaptureStatus = 'ready' | 'processing' | 'no_mentions' | 'failed';

export type MentionCategory = 'book' | 'place' | 'product';

export type Mention = {
  id: string;
  category: MentionCategory;
  title: string;
  subtitle: string | null;
  coverImageUrl: string | null;
  initials: string;
  color: string;
};
```

In the `Capture` type (line 24), replace `books: BookMention[];` with `mentions: Mention[];`.

Replace `visibleBookItems` (lines 62-77) with the following. It drops the `category === 'book'` filter, narrows the category, and keeps the 0.6 floor:

```ts
const MENTION_CATEGORIES: readonly MentionCategory[] = ['book', 'place', 'product'];

function asMentionCategory(value: string): MentionCategory | null {
  return (MENTION_CATEGORIES as readonly string[]).includes(value)
    ? (value as MentionCategory)
    : null;
}

function visibleMentions(items: SourceItemInSavedSource[]): Mention[] {
  return items
    // MIN_VISIBLE_CONFIDENCE is shared across all types for now; revisit per
    // type once we have real place/product extraction quality data.
    .filter((item) => item.confidence === null || item.confidence >= MIN_VISIBLE_CONFIDENCE)
    .filter((item) => compact(item.title))
    .map((item) => ({ item, category: asMentionCategory(item.category) }))
    .filter((entry): entry is { item: SourceItemInSavedSource; category: MentionCategory } =>
      entry.category !== null,
    )
    .sort((left, right) => left.item.position - right.item.position)
    .map(({ item, category }) => ({
      id: item.id,
      category,
      title: item.title.trim(),
      subtitle: compact(item.author),
      coverImageUrl: compact(item.cover_image_url),
      initials: initialsFor(item.title),
      color: colorFor(item.id),
    }));
}
```

Replace `statusFor` (lines 79-87) so its parameter and empty-state value are mention-based:

```ts
function statusFor(savedSourceStatus: SavedSourceStatus, mentions: Mention[]): CaptureStatus {
  if (savedSourceStatus === 'processing') {
    return 'processing';
  }
  if (savedSourceStatus === 'done') {
    return mentions.length > 0 ? 'ready' : 'no_mentions';
  }
  return 'failed';
}
```

In `captureFromSavedSource` (lines 97-112), replace the body's `books` usage:

```ts
export function captureFromSavedSource(savedSource: SavedSourceResponse): Capture {
  const mentions = visibleMentions(savedSource.items);
  return {
    id: savedSource.id,
    creator: 'Instagram',
    creatorHandle: compact(savedSource.source_creator_handle),
    status: statusFor(savedSource.status, mentions),
    thumbnailUrl: thumbnailForSavedSource(savedSource),
    sourceUrl: savedSource.source_url,
    createdAt: savedSource.created_at,
    sourceContextSnippet: null,
    mentions,
    errorMessage: savedSource.error_message,
    skipReason: compact(savedSource.skip_reason),
  };
}
```

(`mergeSavedSourcesWithCaptures` needs no change — it spreads `savedSourceCapture` and only overrides `sourceContextSnippet`.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm run test:captures`
Expected: PASS — prints `capture mapping tests passed`.

- [ ] **Step 5: Commit**

```bash
git add src/captures.ts scripts/test-captures.ts
git commit -m "feat(mobile): generalize capture model to type-neutral mentions"
```

---

## Task 2: Add place and product icons

**Files:**
- Modify: `mobile/src/components/icons.tsx`

**Interfaces:**
- Produces: `PlaceIcon({ color?, size? })` and `ProductIcon({ color?, size? })`, matching the existing `IconProps` signature used by `PlusIcon` etc.

- [ ] **Step 1: Add the icons**

In `mobile/src/components/icons.tsx`, add `MapPin` and `Tag` to the `lucide-react-native` import (line 1-8):

```ts
import {
  ArrowLeft,
  Ellipsis,
  ExternalLink,
  MapPin,
  Plus,
  Tag,
  User,
  type LucideProps,
} from 'lucide-react-native';
```

Then add two exports after `ExternalLinkIcon` (after line 46):

```ts
export function PlaceIcon({ color = '#101A17', size }: IconProps) {
  return <MapPin {...iconProps(color, size)} />;
}

export function ProductIcon({ color = '#101A17', size }: IconProps) {
  return <Tag {...iconProps(color, size)} />;
}
```

- [ ] **Step 2: Verify types**

Run: `npm run typecheck`
Expected: PASS (no errors). Confirms `MapPin` and `Tag` are valid exports of the installed `lucide-react-native`.

- [ ] **Step 3: Commit**

```bash
git add src/components/icons.tsx
git commit -m "feat(mobile): add place and product icons"
```

---

## Task 3: Rename `books.tsx` → `mentions.tsx` with per-category rendering

**Files:**
- Rename + Modify: `mobile/src/components/books.tsx` → `mobile/src/components/mentions.tsx`

**Interfaces:**
- Consumes: `Mention`, `MentionCategory` (Task 1); `PlaceIcon`, `ProductIcon` (Task 2); `BookSpine`, `BookSpineSkeleton` (`mobile/src/components/ui.tsx:136,154`).
- Produces (all consumed by Task 4):
  - `MentionsList({ mentions: Mention[] })`
  - `ProcessingMentions()`
  - `NoMentions({ onOpenSource: () => void; wasSkipped?: boolean })`
  - `FailedState({ isRetrying: boolean; onOpenSource: () => void; onRetry: () => void })` (unchanged behavior)

- [ ] **Step 1: Rename the file**

```bash
git mv src/components/books.tsx src/components/mentions.tsx
```

- [ ] **Step 2: Rewrite the component file**

Replace the entire contents of `mobile/src/components/mentions.tsx` with:

```tsx
import { useEffect, useState } from 'react';
import { Image, Text, View } from 'react-native';

import type { Mention, MentionCategory } from '@/captures';
import { PlaceIcon, ProductIcon } from '@/components/icons';
import { FadeInView } from '@/components/motion';
import { SourceToBooksPreview } from '@/components/product-preview';
import { BookSpine, BookSpineSkeleton, PrimaryButton, SecondaryButton } from '@/components/ui';
import { styles } from '@/styles';

type MentionsListProps = {
  mentions: Mention[];
};

type MentionRowProps = {
  mention: Mention;
  showDivider: boolean;
};

const SECTION_TITLE: Record<MentionCategory, string> = {
  book: 'Books mentioned',
  place: 'Places mentioned',
  product: 'Products mentioned',
};

function sectionTitleFor(mentions: Mention[]): string {
  // Posts are single-type; the first item determines the header.
  return mentions.length > 0 ? SECTION_TITLE[mentions[0].category] : 'Mentions';
}

export function ProcessingMentions() {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Finding mentions...</Text>
      <Text style={styles.sectionSubtitle}>
        Mentioned is checking this post for books, places, and products.
      </Text>
      <View style={styles.skeletonList}>
        <SkeletonMentionRow />
        <SkeletonMentionRow />
      </View>
    </View>
  );
}

function SkeletonMentionRow() {
  return (
    <View style={styles.bookRow}>
      <BookSpineSkeleton />
      <View style={styles.skeletonTextGroup}>
        <View style={[styles.skeletonLine, { width: '78%' }]} />
        <View style={[styles.skeletonLine, { width: '52%' }]} />
        <View style={[styles.skeletonLine, { width: '92%' }]} />
      </View>
    </View>
  );
}

export function MentionsList({ mentions }: MentionsListProps) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{sectionTitleFor(mentions)}</Text>
      <View style={styles.bookListSurface}>
        {mentions.map((mention, index) => (
          <FadeInView key={mention.id} delay={Math.min(index * 55, 220)}>
            <MentionRow mention={mention} showDivider={index < mentions.length - 1} />
          </FadeInView>
        ))}
      </View>
    </View>
  );
}

function MentionTile({ mention }: { mention: Mention }) {
  if (mention.category === 'place') {
    return (
      <View style={[styles.bookSpine, { backgroundColor: mention.color }]}>
        <PlaceIcon color="#FFFFFF" size={22} />
      </View>
    );
  }
  if (mention.category === 'product') {
    return (
      <View style={[styles.bookSpine, { backgroundColor: mention.color }]}>
        <ProductIcon color="#FFFFFF" size={22} />
      </View>
    );
  }
  return <BookSpine color={mention.color} initials={mention.initials} />;
}

function MentionRow({ mention, showDivider }: MentionRowProps) {
  const [didFailCoverLoad, setDidFailCoverLoad] = useState(false);
  const shouldShowCoverImage = Boolean(mention.coverImageUrl) && !didFailCoverLoad;

  useEffect(() => {
    setDidFailCoverLoad(false);
  }, [mention.coverImageUrl]);

  return (
    <View>
      <View style={styles.bookRow}>
        {shouldShowCoverImage && mention.coverImageUrl ? (
          <Image
            source={{ uri: mention.coverImageUrl }}
            resizeMode="cover"
            style={styles.bookCoverImage}
            onError={() => setDidFailCoverLoad(true)}
          />
        ) : (
          <MentionTile mention={mention} />
        )}
        <View style={styles.bookCopy}>
          <Text style={styles.bookTitle}>{mention.title}</Text>
          {mention.subtitle ? <Text style={styles.bookAuthor}>{mention.subtitle}</Text> : null}
        </View>
      </View>
      {showDivider ? <View style={styles.bookRowDivider} /> : null}
    </View>
  );
}

export function NoMentions({
  onOpenSource,
  wasSkipped = false,
}: {
  onOpenSource: () => void;
  wasSkipped?: boolean;
}) {
  return (
    <View style={styles.stateCard}>
      <Text style={styles.stateTitle}>
        {wasSkipped ? 'Nothing to extract from this post' : 'Nothing found in this post'}
      </Text>
      <Text style={styles.stateBody}>
        {wasSkipped
          ? "The post is still saved. This one doesn't look like it features any books, places, or products."
          : "The post is still saved. Mentioned didn't find a clear book, place, or product to show here."}
      </Text>
      <View style={styles.statePreviewWrap}>
        <SourceToBooksPreview />
      </View>
      <View style={styles.stateActions}>
        <SecondaryButton label="Open original" onPress={onOpenSource} compact />
      </View>
    </View>
  );
}

export function FailedState({
  isRetrying,
  onOpenSource,
  onRetry,
}: {
  isRetrying: boolean;
  onOpenSource: () => void;
  onRetry: () => void;
}) {
  return (
    <View style={styles.stateCard}>
      <Text style={styles.stateTitle}>Could not find mentions in this post</Text>
      <Text style={styles.stateBody}>
        The post is still saved. Try again, or open the original.
      </Text>
      <View style={styles.stateActions}>
        <PrimaryButton
          label={isRetrying ? 'Retrying...' : 'Retry'}
          onPress={onRetry}
          compact
          disabled={isRetrying}
        />
        <SecondaryButton label="Open original" onPress={onOpenSource} compact />
      </View>
    </View>
  );
}
```

Notes for the implementer:
- `MentionTile` reuses the existing `styles.bookSpine` tile (a 52×74 colored rounded box) and places a white icon inside it for place/product; books keep the initials `BookSpine`. No new style is required.
- The `ProcessingBooks`, `BooksMentioned`, `NoBooks` names are intentionally gone; Task 4 updates the only importer.

- [ ] **Step 3: Verify types (will fail on the importer until Task 4)**

Run: `npm run typecheck`
Expected: errors ONLY in `src/screens/reel-detail-screen.tsx` (it still imports from `@/components/books`). `mentions.tsx` itself must report no errors. If `mentions.tsx` has errors, fix them before proceeding.

- [ ] **Step 4: Commit**

```bash
git add src/components/mentions.tsx
git commit -m "feat(mobile): render mentions by category with icon-tile placeholders"
```

---

## Task 4: Wire screens and update copy

**Files:**
- Modify: `mobile/src/screens/reel-detail-screen.tsx`
- Modify: `mobile/src/screens/home-screen.tsx`

**Interfaces:**
- Consumes: `MentionsList`, `ProcessingMentions`, `NoMentions`, `FailedState` (Task 3); `Capture.mentions`, `CaptureStatus` `'no_mentions'` (Task 1).

- [ ] **Step 1: Update the detail screen imports**

In `mobile/src/screens/reel-detail-screen.tsx`, replace the import block (lines 6-11):

```tsx
import {
  FailedState,
  MentionsList,
  NoMentions,
  ProcessingMentions,
} from '@/components/mentions';
```

- [ ] **Step 2: Update the detail screen status branches**

In the same file:
- Line 62: replace `<BooksMentioned books={capture.books} />` with `<MentionsList mentions={capture.mentions} />`.
- Line 68: replace `<ProcessingBooks />` with `<ProcessingMentions />`.
- Line 72: replace `capture.status === 'no_books'` with `capture.status === 'no_mentions'`.
- Line 75: replace `<NoBooks onOpenSource={onOpenSource} wasSkipped={Boolean(capture.skipReason)} />` with `<NoMentions onOpenSource={onOpenSource} wasSkipped={Boolean(capture.skipReason)} />`.

- [ ] **Step 3: Update home screen copy**

In `mobile/src/screens/home-screen.tsx`:
- Line 60: replace the subtitle text `Posts you save so Mentioned can find the books inside.` with `Posts you save so Mentioned can find the books, places, and products inside.`
- Line 66: replace `Ready to find books` with `Ready to extract`.
- Line 67-69 (`pendingSourceUrl` text) — leave unchanged (it shows the URL).

- [ ] **Step 4: Verify types across the project**

Run: `npm run typecheck`
Expected: PASS (no errors). This confirms every reference to the renamed `books`/`BookMention`/`no_books` symbols is resolved.

- [ ] **Step 5: Re-run the capture tests**

Run: `npm run test:captures`
Expected: PASS — prints `capture mapping tests passed`.

- [ ] **Step 6: Commit**

```bash
git add src/screens/reel-detail-screen.tsx src/screens/home-screen.tsx
git commit -m "feat(mobile): surface non-book mentions in detail and home screens"
```

---

## Task 5: Update the mobile AGENTS guide if needed

**Files:**
- Modify: `mobile/AGENTS.md` (only if it describes the app as books-only)

**Interfaces:** none.

- [ ] **Step 1: Check the guide**

Run: `grep -in "book" mobile/AGENTS.md`
Expected: lists any book-specific framing. If a line describes the app as showing only books, update it to reflect books/places/products. If no such framing exists, skip to Step 3 (no commit needed).

- [ ] **Step 2: Update and commit (only if Step 1 found book-only framing)**

```bash
git add mobile/AGENTS.md
git commit -m "docs(mobile): note mentions are books, places, and products"
```

- [ ] **Step 3: Final manual verification handoff**

This environment cannot run the Expo app. The implementer must hand the device check to the user:
> Typecheck and `test:captures` pass. Please verify on device: save a known restaurant/place post and a product post, confirm each renders under the correct header ("Places mentioned" / "Products mentioned") with the map-pin / tag icon tile, and that a books post is unchanged.

---

## Self-Review

**Spec coverage:**
- Type-neutral `Mention` model + drop `category` filter → Task 1. ✓
- Drop unused `synopsis` field → Task 1 (new model omits it). ✓
- `no_books` → `no_mentions` rename → Tasks 1, 4. ✓
- Type-icon tile (pin/tag) placeholder → Tasks 2, 3. ✓
- Adaptive single-type section header → Task 3 (`sectionTitleFor`). ✓
- 0.6 floor unchanged + code comment → Task 1. ✓
- Type-neutral processing + empty copy → Tasks 3, 4. ✓
- Home screen copy → Task 4. ✓
- `reel-tile.tsx` needs no logic change (reads only `status`) → flows via the `CaptureStatus` type, covered by Task 4 typecheck. ✓
- Testing: unit (test-captures) + typecheck + manual handoff → Tasks 1, 4, 5. ✓
- Out of scope (backend, enrichment, images, web) → enforced by Global Constraints. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows full code. ✓

**Type consistency:** `Mention.subtitle` (not `author`), `Capture.mentions` (not `books`), `'no_mentions'`, `MentionsList`/`ProcessingMentions`/`NoMentions` used identically across Tasks 1, 3, 4. `styles.bookSpine` reused (verified to exist at `styles.ts:730`). `BookSpine` prop shape (`color?`, `initials`) matches `ui.tsx:136`. ✓
