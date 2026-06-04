# PRD: Release 1 iOS-First Published Proof

Date: 2026-05-28
Status: Draft
Product: Mentioned

## Problem Statement

Recommendation collectors already save social content because it contains useful recommendations, but saved folders quickly become unsearchable piles. A user may save a Reel with book recommendations, then later struggle to remember which books were mentioned or where the source went.

Mentioned currently proves the extraction loop through pasted Instagram/Reel links, but the product does not yet feel like the natural way to save from a social app. For the first published proof, Mentioned needs to become an installable iOS app that appears in the share sheet, accepts a shared source, extracts books, and lets the user reopen the saved result later.

The goal is not to launch the full semantic memory product yet. The goal is to publish a trustworthy small app that proves the native capture core loop and can be shown as a real store-distributed product.

## Solution

Release 1 makes Mentioned an iOS-first published proof for the book-first wedge.

Users should be able to share a supported Instagram/Reel source to Mentioned from the iOS share sheet. Mentioned should save the source, run the existing extraction pipeline, show processing state, and then display extracted books as the primary result on the saved source detail screen. The home screen should organize around saved sources. Paste-link capture remains available as a fallback, but native capture is the main story.

The experience should meet the "trustworthy small app" bar: intentional UI, clear loading and failure states, auth and privacy basics, recoverable errors, and no obvious broken flows. Extraction may be useful but imperfect. Users should have basic correction controls for wrong or incomplete results, without turning Release 1 into a full catalog management product.

## Goals

- Publish an iOS-first app proof that can be installed and shown.
- Make native share-sheet capture the primary way to save a source.
- Preserve the current books-from-source extraction loop.
- Keep the app organized around saved sources for Release 1.
- Prioritize extracted books on saved source detail.
- Support useful but imperfect extraction through clear states and basic correction.
- Keep future product vision subtle in the app without showing unavailable feature surfaces.

## Non-Goals

- Semantic search.
- User-curated collections.
- Non-book categories such as places, recipes, products, posts, or memes.
- Android or Google Play release.
- Advanced item/catalog editing.
- Major scale or cost optimization beyond basic safety guardrails.
- A portfolio-quality promotional launch.

## User Stories

1. As a recommendation collector, I want Mentioned to appear in the iOS share sheet, so that I can save a source without copying and pasting a link manually.
2. As a recommendation collector, I want to share an Instagram/Reel source to Mentioned, so that the app can find the books mentioned in it.
3. As a recommendation collector, I want the app to confirm that a shared source was accepted, so that I know the save action worked.
4. As a recommendation collector, I want shared sources to appear on my home screen, so that I can return to them later.
5. As a recommendation collector, I want the home screen to show saved sources first, so that the app matches the way I originally saved content.
6. As a recommendation collector, I want to open a saved source and see extracted books first, so that I can quickly get the useful recommendations.
7. As a recommendation collector, I want the original source link to remain available, so that I can reopen the Reel/post if I need more context.
8. As a recommendation collector, I want a processing state after saving a source, so that I understand extraction is still running.
9. As a recommendation collector, I want a failure state with a retry action, so that a temporary extraction issue does not feel like data loss.
10. As a recommendation collector, I want a no-books state when no useful books were found, so that the app explains the outcome clearly.
11. As a recommendation collector, I want paste-link capture to remain available, so that I have a fallback if native sharing fails or I already copied a URL.
12. As a signed-out user, I want the app to handle a shared source gracefully, so that I do not lose the source while signing in.
13. As a signed-in user, I want saved sources and extracted books to persist across app restarts, so that Mentioned feels like a real archive.
14. As a signed-in user, I want my saved sources to be private to my account, so that other users cannot see my saved content.
15. As a user, I want book rows to show enough information to recognize each book, so that the extraction result feels useful.
16. As a user, I want obvious wrong books to be removable, so that bad extraction results do not pollute my saved source.
17. As a user, I want simple manual correction for a wrong title or author, so that I can fix an otherwise useful result.
18. As a user, I want to mark a result as wrong, so that the app has a lightweight feedback path for extraction quality.
19. As a user, I want retry to be available on failed sources, so that temporary provider or download failures can recover.
20. As a user, I want error messages to be calm and understandable, so that I know whether the problem is unsupported content, network failure, auth, or extraction.
21. As a user, I want the app to avoid showing raw provider details, confidence scores, or backend artifacts, so that the UI feels consumer-facing.
22. As a user, I want source evidence to be lightweight, so that I can see where a book came from without reading an extraction audit trail.
23. As a user, I want the app copy to hint that collections and search may come later, so that the vision is visible without dead controls.
24. As a user, I do not want disabled tabs for unavailable features, so that the app feels finished for what it currently does.
25. As a tester, I want to install the app through an Apple-distributed path, so that I can use it without a local developer setup.
26. As the product owner, I want the first release to prove installability, native capture, and the extraction loop, so that the next version can build from a real store pipeline.
27. As the product owner, I want Release 1 scope to stay narrow, so that semantic search, collections, and category expansion do not block publication.
28. As the product owner, I want the app to be good enough to show but not necessarily market broadly, so that the first release does not stall on portfolio-level polish.
29. As an operator, I want basic logs and job status visibility, so that extraction failures can be diagnosed during early use.
30. As an operator, I want basic usage guardrails, so that a small number of users cannot accidentally create unbounded provider cost.

## Implementation Decisions

- Release 1 is iOS-first. Android and Google Play are intentionally deferred.
- Native capture is required for Release 1. Paste-link capture remains as a fallback.
- Native capture should accept shared text or URLs from the iOS share sheet, extract a supported source URL, and move the user into the existing save/extraction flow.
- The first supported content category remains books. The product should not introduce places, recipes, products, posts, memes, or other categories in Release 1.
- The first supported source path remains the current Instagram/Reel-style flow. The product language may avoid overcommitting to Instagram long term, but Release 1 should not attempt multi-platform extraction.
- The app home remains saved-source first. A books-first library, collection-first home, and activity timeline are out of scope for Release 1.
- Saved source detail should be results-first. Extracted books are the primary content; source context and source-opening actions are secondary.
- Extracted items remain source history. Release 1 does not create user-curated collections.
- Extraction quality bar is useful but imperfect. The app should handle misses, wrong results, empty results, and failures clearly.
- Basic correction is in scope: remove wrong items, retry failed sources, make simple manual edits, and mark a result as wrong.
- Advanced editing is out of scope: cover management, ISBN management, category recategorization, source metadata editing, and full catalog workflows should wait.
- Auth and privacy basics are part of the trustworthy app bar. Saved sources and extracted items must remain scoped to the signed-in user.
- Store publication is part of the milestone. The release is not complete if it only runs locally.
- The app may subtly hint at the larger collections and semantic memory direction, but it should not show disabled feature screens.
- The backend should continue to own extraction, enrichment, persistence, and job status. The mobile app should not duplicate extraction logic.
- The mobile app should continue to treat provider details, confidence scores, raw transcripts, artifact paths, and backend internals as non-user-facing implementation details.
- Operationally, Release 1 should prefer simple guardrails over major cost optimization. Full scale/cost redesign is deferred.

## Testing Decisions

Tests should focus on externally visible behavior, not implementation details.

- Native capture tests should verify that shared text containing a supported URL produces the same user-visible result as manually submitting that URL.
- Native capture should be manually verified on an iOS simulator or device from at least one app that can invoke the system share sheet.
- Signed-in capture should be verified end to end: share source, create job, show processing state, complete extraction, reopen saved source.
- Signed-out capture should be verified for graceful handling: the shared source should not disappear silently if auth is required.
- Paste-link fallback should keep passing existing mobile and backend behavior.
- Job flow tests should continue to cover create, list, detail, pending, done, failed, and user ownership behavior.
- Correction behavior should be covered with tests for removing an extracted item, updating simple fields, retrying failed sources, and marking a result as wrong if that feedback path is persisted.
- Backend tests should keep provider calls deterministic through fixtures, monkeypatching, or offline fakes.
- At least one live smoke test with a real supported public source should be run before store submission, with provider credentials configured locally or in staging.
- Mobile type checks should pass before release.
- Backend tests should pass before release.
- Store readiness should be manually checked: app icon, splash screen, privacy policy URL, auth callback, production API URL, production Supabase config, app metadata, screenshots, and reviewer notes.

## Success Criteria

- Mentioned appears in the iOS share sheet for compatible shared content.
- A user can share a supported Instagram/Reel source into Mentioned.
- A saved source appears in the app after native capture.
- The app shows processing while extraction runs.
- Extracted books appear first on the saved source detail screen.
- The original source remains reopenable.
- Failed and no-book outcomes are clear and recoverable where possible.
- Basic correction controls exist for wrong or incomplete extraction.
- The app is installable through an Apple-distributed path.
- Release 1 does not expose semantic search, collections, non-book categories, Android, or advanced editing.

## Out of Scope

- Semantic source recall.
- Item lookup across saved sources.
- Vague memory search.
- Mixed item/source search results.
- User-curated collections.
- AI-generated reading lists or itineraries.
- Travel, recipes, restaurants, products, posts, memes, outfits, quotes, or other item types.
- Android share intents.
- Google Play release.
- Full website or waitlist experience.
- Provider cost redesign.
- Queue architecture redesign.
- Full analytics platform.
- Full admin/support tooling.

## Further Notes

Release 1 should be treated as a store-distributed proof, not the final consumer-polished product. The next product jump after publication should make the app consumer-polished and introduce semantic source recall as the marquee feature.

The long-term product promise remains: save social recommendations into useful collections. The internal north star remains: become the semantic memory layer for everything the user saves online.
