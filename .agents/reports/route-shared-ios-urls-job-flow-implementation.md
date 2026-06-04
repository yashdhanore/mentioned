# Implementation Report: Route Shared iOS URLs Into Job Creation

**GitHub Issue**: #14

## Summary

Implemented native iOS share handoff as direct mobile job creation. Valid `mentioned://share` deep links now create jobs through the existing `POST /v1/jobs` client path, insert/select the optimistic processing capture, and avoid opening the paste sheet. Paste-link capture still uses the same create-job flow and keeps paste-specific errors in the paste sheet.

## Tasks Completed

| Task | Status | Notes |
|------|--------|-------|
| Harden shared deep-link parsing and handoff encoding | Complete | Added discriminated parsing for valid, invalid share, and non-share links. Encoded source URL in the share extension handoff. |
| Factor capture submission inside `useCaptures` | Complete | Added shared helper for create-job submission, optimistic insertion, selection, and refresh. Added shared-capture loading/error API. |
| Wire host-app deep links to direct job creation | Complete | Added pending shared URL state, auth-gated submission, and duplicate raw deep-link guard. |
| Surface invalid or failed shared-capture errors calmly | Complete | Invalid share links and shared submission failures render through the home inline error surface without a misleading refresh action. |
| Preserve paste-link capture behavior | Complete | Paste submission still trims/validates input, calls `createJob`, inserts/selects processing capture, clears input, closes the sheet on success, and keeps paste errors in the sheet. |

## Validation

| Command | Result |
|---------|--------|
| `cd mobile && npm run test:share-url` | Passed |
| `cd mobile && npm run typecheck` | Passed |

## Files Changed

| File | Purpose |
|------|---------|
| `mobile/src/utils/shared-source-url.ts` | Added discriminated deep-link parsing while preserving the existing wrapper. |
| `mobile/scripts/test-share-url-extraction.ts` | Added coverage for non-share links, invalid share links, malformed share links, and encoded source URLs with retained query params. |
| `mobile/ShareExtension.tsx` | Encoded the source URL when opening the host app. |
| `mobile/src/features/captures/use-captures.ts` | Factored create-job submission and added shared-capture state/API. |
| `mobile/App.tsx` | Routed valid share deep links to auth-gated direct job creation with duplicate guarding and home-surface errors. |
| `mobile/src/screens/home-screen.tsx` | Made inline error actions optional/customizable. |

## Deviations From Plan

None.

## Follow-Ups

Manual iOS share-extension smoke testing still needs a signed-in native session and running backend.
