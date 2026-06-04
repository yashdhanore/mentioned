# Plan: Route Shared iOS URLs Into Job Creation

## Summary

Issue 14 should move the current iOS share-extension handoff from "prefill the paste sheet" to "submit the shared source through the same job creation path as paste-link capture." The change is mobile-only: keep the backend API unchanged, reuse `POST /v1/jobs`, insert the same optimistic processing capture, select/open that capture, and keep paste-link capture working.

## Request Parse

- Problem: `mentioned://share?url=...` links are parsed by the host app but only staged in the paste sheet, so native capture does not create a backend job.
- User story: as a signed-in user sharing a supported Instagram Reel/post URL into Mentioned, I should see it saved immediately as a processing capture and be taken to its detail screen.
- Scope: signed-in native share capture, deep-link validation, duplicate deep-link guard, shared-submission error handling, paste-flow preservation.
- Out of scope: durable signed-out pending-source persistence, backend schema/API changes, Android share intents, extraction pipeline changes.
- Risk level: medium, because deep links can arrive before auth restoration and duplicate URL events can create duplicate backend jobs.

## Issue

- GitHub Issue: #14
- URL: https://github.com/yashdhanore/mentioned/issues/14

## Patterns To Follow

| Area | Source | Pattern |
|------|--------|---------|
| Job creation | `mobile/src/features/captures/use-captures.ts` | Paste capture calls `createJob`, builds an optimistic processing capture with `captureFromJobCreated`, places it first, selects it, clears input state, then refreshes by job id. |
| Backend contract | `mobile/src/api.ts` | `createJob(url)` posts `{ url }` to `/v1/jobs` and relies on the shared auth header provider. No new API client method is needed. |
| Source URL parsing | `mobile/src/utils/shared-source-url.ts` | Shared URL utilities normalize supported HTTPS Instagram `/reel/` and `/p/` URLs and reject unsupported content. |
| Share handoff | `mobile/ShareExtension.tsx` | The extension extracts a URL from native props and opens the host app through the `mentioned://share` route. |
| User-facing errors | `mobile/src/components/ui.tsx` and `mobile/src/screens/home-screen.tsx` | Use `InlineMessage` for calm inline errors instead of raw provider/backend details. |
| Server validation | `src/jobs/router.py` and `src/extraction/url.py` | Backend remains the final validator and normalizer for source URLs, quota, rate limit, and job ownership behavior. |

## Files To Change

| File | Action | Purpose |
|------|--------|---------|
| `mobile/src/utils/shared-source-url.ts` | UPDATE | Add a parse result that distinguishes valid share links, invalid share links, and non-share links, while preserving existing `sharedUrlFromMentionedDeepLink` behavior. |
| `mobile/scripts/test-share-url-extraction.ts` | UPDATE | Cover invalid share deep links, non-share deep links, and encoded source URLs with retained non-tracking query params. |
| `mobile/ShareExtension.tsx` | UPDATE | Encode the source URL in `openHostApp("share?url=...")` so retained source query params cannot be truncated by the host deep link. |
| `mobile/src/features/captures/use-captures.ts` | UPDATE | Factor paste submission into a reusable source URL submission helper and expose a shared-capture submit/error API. |
| `mobile/App.tsx` | UPDATE | Submit valid `mentioned://share` URLs after auth has settled, guard duplicate deep-link handling, close paste UI on share success, and surface invalid shared-content errors. |
| `mobile/src/screens/home-screen.tsx` | UPDATE | Let home inline errors have optional/custom actions so load errors can keep "Try again" while shared-capture errors can be shown without a misleading refresh action. |

## Tasks

1. Harden shared deep-link parsing and handoff encoding
   - Files: `mobile/src/utils/shared-source-url.ts`, `mobile/scripts/test-share-url-extraction.ts`, `mobile/ShareExtension.tsx`
   - Details:
     - Add a small discriminated parse helper, for example `parseMentionedShareDeepLink(rawUrl)`, returning valid source URL, invalid share link, or non-share link.
     - Keep `sharedUrlFromMentionedDeepLink(rawUrl)` as a compatibility wrapper returning `string | null`.
     - Add tests that prove auth callback links are ignored, malformed/unsupported `mentioned://share` links are classified as invalid, and encoded URLs with retained params survive parsing.
     - Change share-extension handoff to `openHostApp(\`share?url=${encodeURIComponent(sourceUrl)}\`)`.
   - Validate:
     - `cd mobile && npm run test:share-url`

2. Factor capture submission inside `useCaptures`
   - Files: `mobile/src/features/captures/use-captures.ts`
   - Details:
     - Add an internal helper that accepts a normalized source URL and error-copy options, calls `createJob`, inserts `captureFromJobCreated(created.job_id, sourceUrl)` at the top, selects it, and calls `refreshCaptureById(created.job_id)`.
     - Update `submitPasteUrl()` to delegate to that helper so paste behavior stays unchanged.
     - Add a share-specific public method, for example `submitSharedUrl(sourceUrl): Promise<boolean>`.
     - Add share-specific state such as `sharedCaptureError`, `isSubmittingSharedUrl`, and `clearSharedCaptureError` rather than overloading `pasteError`.
     - Keep `retryCapture()` behavior unchanged unless the helper can be reused without widening scope.
   - Validate:
     - `cd mobile && npm run typecheck`

3. Wire host-app deep links to direct job creation
   - Files: `mobile/App.tsx`
   - Details:
     - Replace the current `setPasteUrl(sharedUrl); setSheet('paste')` behavior with storing a pending shared URL.
     - Use an effect that waits for `isAuthLoading === false` and `isSignedIn === true` before calling `submitSharedUrl(pendingSharedUrl)`.
     - On success, clear the pending URL, close the paste sheet if it is open, and rely on selected capture state to open the processing detail.
     - If auth resolves signed out, show calm sign-in copy through existing auth error state, but do not add durable local persistence; issue 15 owns that.
     - Add an in-memory duplicate guard for raw share deep links so `getInitialURL()` and the URL event cannot submit the same link twice during the same launch.
   - Validate:
     - `cd mobile && npm run typecheck`

4. Surface invalid or failed shared-capture errors calmly
   - Files: `mobile/App.tsx`, `mobile/src/screens/home-screen.tsx`
   - Details:
     - For invalid `mentioned://share` links, set a user-facing message such as "Share an Instagram Reel or post link to save it."
     - For backend/network failures from `submitSharedUrl`, show `errorMessage(error, "Could not save that shared source.")` in the home surface.
     - Extend `HomeScreen` error props so load errors can still show `Try again`, while share errors can render without a refresh action or with an appropriate retry path if the URL is retained.
     - Clear shared-capture errors when a new valid share is submitted, when the user opens paste capture, and after successful submission.
   - Validate:
     - `cd mobile && npm run typecheck`

5. Preserve paste-link capture behavior
   - Files: `mobile/src/features/captures/use-captures.ts`, `mobile/App.tsx`
   - Details:
     - Confirm paste-link submission still validates empty input, uses `createJob`, inserts a processing capture at the top, selects it, clears `pasteUrl`, closes the paste sheet on success, and keeps paste errors in the paste sheet.
     - Do not change `createJob` request shape or backend routes.
   - Validate:
     - Manual paste-link smoke check, or at minimum `cd mobile && npm run typecheck`.

## Validation

```bash
cd mobile
npm run test:share-url
npm run typecheck
```

Manual validation:

1. Start the API with a signed-in mobile session available.
2. Share a supported Instagram Reel/post URL into Mentioned from iOS.
3. Confirm the host app creates a `/v1/jobs` job, inserts the new processing capture at the top, and opens/selects that capture.
4. Share unsupported text or a non-Instagram URL and confirm the user sees calm unsupported-source copy.
5. Paste a supported URL through the paste sheet and confirm the existing flow still works.
6. Trigger the same share deep link twice quickly and confirm only one job is created.

## Acceptance Criteria

- [ ] Shared text/URL payloads are parsed for a supported source URL.
- [ ] Valid shared URLs call the same `POST /v1/jobs` path as paste-link capture.
- [ ] Newly created shared captures appear at the top of saved source home state.
- [ ] The app selects/opens the new processing capture after successful native capture.
- [ ] Invalid shared content shows calm user-facing error copy.
- [ ] Paste-link capture continues to work.
- [ ] `cd mobile && npm run test:share-url` passes.
- [ ] `cd mobile && npm run typecheck` passes.
- [ ] Generated/runtime artifacts are not staged.
