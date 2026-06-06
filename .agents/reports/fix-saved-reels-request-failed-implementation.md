# Implementation Report: Fix Saved Reels Request Failed

**GitHub Issue**: N/A

## Summary

Changed the mobile Saved Reels home refresh to build grid captures directly from `GET /v1/jobs` list items. Per-job `GET /v1/jobs/{id}` detail requests remain in detail/realtime/retry/delete flows, so opening a Reel still refreshes full mention data without the home-screen N+1 burst.

## Tasks Completed

| Task | Status | Notes |
|------|--------|-------|
| Add failing pure capture-mapping test | Complete | Added `mobile/scripts/test-captures.ts` and `npm run test:captures`; confirmed it failed before mapper implementation because `captureFromJobListItem` was missing. |
| Implement list-item capture conversion | Complete | Added `captureFromJobListItem()` and `buildCapturesFromJobList()` with list statuses mapped to grid states. |
| Remove home-grid detail fan-out | Complete | `refreshCaptures()` now calls `listAllJobs()` and sets captures from list items without `Promise.all()` or `getJob()`. |
| Add source-level fan-out regression | Complete | Added pytest coverage that isolates `refreshCaptures()` and confirms detail refresh still calls `getJob(jobId)`. |
| Validate focused fix | Complete | Focused mobile/Python validation and full pytest suite pass. |
| Manual hosted smoke | Not run | Render CLI log checks ran and showed historical QueuePool/500 entries; interactive signed-in iOS smoke requires a device/account session. |

## Validation

| Command | Result |
|---------|--------|
| `cd mobile && npm run test:captures` | Pass: `capture mapping tests passed` |
| `cd mobile && npm run typecheck` | Pass |
| `.venv/bin/python -m pytest tests/test_mobile_signed_out_screen.py` | Pass: 9 passed |
| `.venv/bin/python -m pytest` | Pass: 104 passed, 4 skipped |
| `render logs -r srv-d7vmctfaqgkc739dl910 --text "QueuePool" --limit 10 -o text` | Ran; showed historical QueuePool timeout entries. |
| `render logs -r srv-d7vmctfaqgkc739dl910 --text "500" --limit 10 -o text` | Ran; showed historical 500 entries including `/v1/jobs/{id}`. |

## Files Changed

| File | Purpose |
|------|---------|
| `mobile/src/captures.ts` | Add list-item-to-capture conversion and preserve existing detail conversion. |
| `mobile/src/features/captures/use-captures.ts` | Use list-only capture mapping for home refresh. |
| `mobile/scripts/test-captures.ts` | Cover list-item and detail capture mapping behavior. |
| `mobile/package.json` | Add `test:captures` script. |
| `tests/test_mobile_signed_out_screen.py` | Add request fan-out source regression. |

## Deviations From Plan

- Created an isolated implementation worktree at `.worktrees/fix-saved-reels-request-failed` because the original workspace was on `main` with unrelated changes.
- Used `python3` and an ignored worktree `.venv` because `python` and pytest were not available on PATH.
- Did not run the interactive iOS signed-in smoke test; it needs a logged-in account with saved Reels.

## Follow-Ups

- Run the signed-in device/simulator smoke against the hosted backend after deploying this branch.
- Continue tracking backend pool timeouts separately, since other high-concurrency paths can still exhaust the pool.
