# Plan: Fix iOS Book Cover Thumbnails

## Summary

Fix the native iOS simulator failure where Reel detail pages show extracted books but blank book cover thumbnails, while Expo web renders the same covers. The focused fix is to normalize Google Books cover URLs to HTTPS before persisting them and to make the mobile book row fall back to the generated `BookSpine` when React Native image loading fails.

This plan intentionally does not add iOS ATS exceptions. The app should return and render mobile-safe image URLs instead of weakening native transport policy.

## Scope

- In:
  - Normalize Google Books `imageLinks` cover URLs from `http://books.google.com/...` to `https://books.google.com/...`.
  - Preserve existing HTTPS cover URLs unchanged.
  - Add a native mobile fallback so failed cover loads render `BookSpine` instead of a blank image area.
  - Add focused backend regression tests for Google Books cover URL normalization.
  - Run targeted backend tests, mobile capture tests, and mobile typecheck.
- Out:
  - The saved-reels request burst issue documented in `tofix.md`.
  - Adding iOS `NSAppTransportSecurity` arbitrary-load or domain exceptions.
  - Creating a new Supabase Storage bucket for book covers.
  - Server-side cover image downloading, re-hosting, or RGB transcoding.
  - Backfilling already persisted `books.cover_image_url` or `mentions.cover_image_url` rows.
  - Replacing React Native `Image` with a third-party image library.

## Issue

- GitHub Issue: N/A
- URL: N/A

## Failure Mode

The backend copies `volumeInfo.imageLinks` from Google Books into `Book.cover_image_url`, then into `Mention.cover_image_url`, and the mobile app maps that value to `BookMention.coverImageUrl`. `mobile/src/components/books.tsx` passes the URL directly into React Native `Image`.

Google Books commonly returns cover URLs like `http://books.google.com/books/content?...`. Web can often load these, but native iOS can block non-HTTPS image loads or fail low-level image decoding. The terminal warning `CMPhotoJFIFUtilities signalled err=-17102` is consistent with iOS image decode/load problems, and `BookRow` currently has no `onError` fallback.

## Patterns To Follow

| Area | Source | Pattern |
|------|--------|---------|
| Google Books parsing | `src/extraction/google_books.py` | Keep provider response parsing in small pure helper functions near `_image_links()` and `_cover_image_url()`. |
| Backend tests | `tests/extraction/test_google_books.py` | Use `respx` to mock `GOOGLE_BOOKS_API` and assert `BookEnrichment` fields. |
| Book persistence | `src/books/service.py` | Persist `GoogleBook.cover_image_url` through the existing `cover_image_url` field without schema changes. |
| Worker enrichment | `src/worker.py` | Worker copies `book.cover_image_url` to `mention.cover_image_url`; no worker contract change needed if parsing normalizes first. |
| Mobile mapping | `mobile/src/captures.ts` | Keep API response mapping pure; `coverImageUrl` remains nullable and comes from `mention.cover_image_url`. |
| Book row rendering | `mobile/src/components/books.tsx` | Render a real cover when available and generated `BookSpine` when unavailable. Extend this existing fallback to image-load failure. |
| Mobile validation | `mobile/package.json` | Use `npm run typecheck` and existing small `tsx` scripts for focused checks. |

## Files To Change

| File | Action | Purpose |
|------|--------|---------|
| `tests/extraction/test_google_books.py` | UPDATE | Add failing regression coverage for `http://books.google.com/...` cover URLs being normalized to HTTPS. |
| `src/extraction/google_books.py` | UPDATE | Add a small cover URL normalization helper and apply it inside `_cover_image_url()`. |
| `mobile/src/components/books.tsx` | UPDATE | Track per-row image load failure and fall back to `BookSpine`. |
| `mobile/scripts/test-captures.ts` | UPDATE | Adjust/add a mapping assertion only if needed; the current capture mapping already preserves `cover_image_url`. |

## Tasks

1. Add a failing backend regression test for Google Books HTTP cover URLs.
   - Files:
     - `tests/extraction/test_google_books.py`
   - Details:
     - Add a `respx` test beside `test_enrich_book_found()`.
     - Mock `imageLinks.thumbnail` as a common Google Books HTTP content URL.
     - Assert `enrich_book()` returns the same URL with an `https://` scheme.
   - Suggested test:

     ```python
     @respx.mock
     async def test_enrich_book_normalizes_google_books_cover_url_to_https():
         respx.get(GOOGLE_BOOKS_API).mock(
             return_value=Response(
                 200,
                 json={
                     "totalItems": 1,
                     "items": [
                         {
                             "id": "abc123",
                             "volumeInfo": {
                                 "title": "Atomic Habits",
                                 "authors": ["James Clear"],
                                 "imageLinks": {
                                     "thumbnail": (
                                         "http://books.google.com/books/content"
                                         "?id=abc123&printsec=frontcover&img=1&zoom=1&source=gbs_api"
                                     )
                                 },
                             },
                         }
                     ],
                 },
             )
         )

         result = await enrich_book("Atomic Habits", "James Clear")

         assert result.cover_image_url == (
             "https://books.google.com/books/content"
             "?id=abc123&printsec=frontcover&img=1&zoom=1&source=gbs_api"
         )
     ```

   - Validate:

     ```bash
     python -m pytest tests/extraction/test_google_books.py::test_enrich_book_normalizes_google_books_cover_url_to_https -q
     ```

     Expected before implementation: fail because the returned URL still starts with `http://`.

2. Implement Google Books cover URL normalization.
   - Files:
     - `src/extraction/google_books.py`
   - Details:
     - Add top-level imports:

       ```python
       from urllib.parse import urlparse, urlunparse
       ```

     - Add a focused helper near `_image_links()`:

       ```python
       def _normalize_cover_image_url(value: str) -> str | None:
           raw_url = value.strip()
           if not raw_url:
               return None

           try:
               parsed = urlparse(raw_url)
           except ValueError:
               return None

           hostname = (parsed.hostname or "").casefold()
           if parsed.scheme == "http" and hostname == "books.google.com":
               return urlunparse(parsed._replace(scheme="https"))
           if parsed.scheme == "https":
               return raw_url
           return None
       ```

     - Update `_cover_image_url()` to normalize the first available cover candidate:

       ```python
       def _cover_image_url(image_links: dict[str, str]) -> str | None:
           for key in ("thumbnail", "smallThumbnail", "small", "medium", "large", "extraLarge"):
               if image_links.get(key):
                   normalized_url = _normalize_cover_image_url(image_links[key])
                   if normalized_url:
                       return normalized_url
           return None
       ```

     - Keep HTTPS URLs from non-Google hosts unchanged because tests and local fixtures use examples like `https://books.example/atomic.jpg`.
     - Return `None` for unsupported schemes so mobile falls back to `BookSpine` rather than trying `http://` or malformed URLs.
   - Validate:

     ```bash
     python -m pytest tests/extraction/test_google_books.py -q
     ```

     Expected after implementation: all Google Books tests pass.

3. Add mobile fallback on book cover image load failure.
   - Files:
     - `mobile/src/components/books.tsx`
   - Details:
     - Import React state helpers:

       ```ts
       import { useEffect, useState } from 'react';
       ```

     - Keep the existing React Native import:

       ```ts
       import { Image, Text, View } from 'react-native';
       ```

     - Update `BookRow` so it resets failure state when the cover URL changes and falls back to `BookSpine` after an `Image` error:

       ```tsx
       function BookRow({ book, isRemoving, showDivider, onOpenRemoveBook }: BookRowProps) {
         const [didFailCoverLoad, setDidFailCoverLoad] = useState(false);
         const shouldShowCoverImage = Boolean(book.coverImageUrl) && !didFailCoverLoad;

         useEffect(() => {
           setDidFailCoverLoad(false);
         }, [book.coverImageUrl]);

         return (
           <View>
             <View style={styles.bookRow}>
               {shouldShowCoverImage && book.coverImageUrl ? (
                 <Image
                   source={{ uri: book.coverImageUrl }}
                   resizeMode="cover"
                   style={styles.bookCoverImage}
                   onError={() => setDidFailCoverLoad(true)}
                 />
               ) : (
                 <BookSpine color={book.color} initials={book.initials} />
               )}
               {/* existing row copy/actions stay unchanged */}
             </View>
             {showDivider ? <View style={styles.bookRowDivider} /> : null}
           </View>
         );
       }
       ```

     - Do not add console logging from `onError`; the iOS terminal is already noisy and the fallback should be user-facing.
   - Validate:

     ```bash
     cd mobile && npm run typecheck
     ```

     Expected: TypeScript passes.

4. Confirm capture mapping still preserves cover URLs.
   - Files:
     - `mobile/scripts/test-captures.ts`
     - `mobile/src/captures.ts`
   - Details:
     - The existing script already creates a detailed capture with `cover_image_url: 'https://books.example/atomic.jpg'`.
     - Add an assertion only if it is missing:

       ```ts
       assert.equal(mergedCaptures[0].books[0].coverImageUrl, 'https://books.example/atomic.jpg');
       ```

     - No production mapping change should be needed because `visibleBookMentions()` already maps `cover_image_url` to `coverImageUrl`.
   - Validate:

     ```bash
     cd mobile && npm run test:captures
     ```

     Expected: `capture mapping tests passed`.

5. Run focused validation.
   - Files:
     - No additional edits expected.
   - Details:
     - Run backend Google Books tests:

       ```bash
       python -m pytest tests/extraction/test_google_books.py -q
       ```

     - Run worker book persistence coverage to ensure normalized cover URLs still flow through book and mention persistence:

       ```bash
       python -m pytest tests/test_worker_books.py -q
       ```

     - Run mobile pure mapping and typecheck:

       ```bash
       cd mobile && npm run test:captures && npm run typecheck
       ```

   - Expected:
     - All commands pass.

6. Manually verify in the iOS simulator.
   - Files:
     - No code edits.
   - Details:
     - Start the app using the same native flow that reproduced the issue:

       ```bash
       cd mobile && npm run ios
       ```

     - Open a saved Reel detail with extracted books.
     - Confirm book rows do not show blank cover boxes.
     - For newly processed jobs, confirm covers load when Google Books returns HTTPS-normalized URLs.
     - If an individual image still fails native decoding, confirm the row displays the generated spine fallback instead of a blank area.
   - Expected:
     - Extracted books remain visible.
     - Book cover area is either a loaded cover image or a generated spine, never a blank broken image.

## Validation

```bash
python -m pytest tests/extraction/test_google_books.py -q
python -m pytest tests/test_worker_books.py -q
cd mobile && npm run test:captures && npm run typecheck
cd mobile && npm run ios
```

## Risks

- Existing rows already persisted with `http://books.google.com/...` will not be normalized by this change until the job/book is re-enriched. If old rows must be fixed, add a separate data migration or one-off maintenance script.
- HTTPS normalization fixes ATS-style native blocking but may not fix every iOS decoder failure. The mobile fallback covers those cases by avoiding a blank UI.
- Full cover re-hosting/transcoding would be more robust, but it requires decisions about a storage bucket, allowed hosts, cache policy, possible `Pillow` dependency, and whether to backfill existing records.

## Acceptance Criteria

- [ ] Google Books HTTP cover URLs are persisted and returned as HTTPS URLs for newly enriched books.
- [ ] Existing HTTPS cover URLs continue to pass through unchanged.
- [ ] Unsupported or malformed cover URL schemes become `None` rather than being rendered by mobile.
- [ ] iOS book rows fall back to `BookSpine` after native image load failure.
- [ ] Backend Google Books tests pass.
- [ ] Worker book persistence tests pass.
- [ ] Mobile capture script and typecheck pass.
- [ ] iOS simulator no longer shows blank book thumbnail boxes on Reel detail.
- [ ] Generated/runtime artifacts are not staged.

