# Implementation Report: Mobile Remove Controls

**GitHub Issue**: #17

## Summary

Added a delete-only mobile correction flow for extracted books. Ready-state book rows now expose a remove action, a confirmation sheet handles the destructive action and inline errors, and the mobile capture state refreshes from the backend after successful deletion so the UI updates without restarting.

## Tasks Completed

| Task | Status | Notes |
|------|--------|-------|
| Add mention delete API helper | Done | Added `deleteMention()` and `DeleteMentionResponse` in `mobile/src/api.ts`. |
| Add remove mutation to `useCaptures` | Done | Added `removingBookId`, `removeBookMention()`, refresh-on-success, and calm error handling. |
| Add row remove entry points | Done | Ready-state book rows can open the remove flow and disable the active row action while removing. |
| Add remove sheet | Done | Added `RemoveBookSheet` with selected-book summary, destructive row, loading label, and inline errors. |
| Wire detail screen props | Done | `ReelDetailScreen` passes remove props only through the ready-state `BooksMentioned` path. |
| Wire app-level selected book state | Done | `App.tsx` owns selected book, removal errors, stale selection cleanup, and sheet rendering. |
| Review backend delete coverage | Done | Existing backend delete/list exclusion tests cover the delete contract; backend production code was unchanged. |

## Validation

| Command | Result |
|---------|--------|
| `cd mobile && npm run typecheck` | Passed |
| `python -m pytest tests/mentions` | Passed, 8 tests; 1 existing Starlette multipart deprecation warning |

## Files Changed

| File | Purpose |
|------|---------|
| `mobile/src/api.ts` | Added typed mention delete API helper. |
| `mobile/src/features/captures/use-captures.ts` | Added book removal mutation state, refresh, and error handling. |
| `mobile/src/components/books.tsx` | Added ready-row remove action affordance. |
| `mobile/src/components/sheets.tsx` | Added remove confirmation sheet. |
| `mobile/src/screens/reel-detail-screen.tsx` | Passed remove props to ready-state book rows. |
| `mobile/App.tsx` | Wired selected book state, remove sheet, and mutation callbacks. |
| `mobile/src/styles.ts` | Added row action and remove-sheet summary styles. |

## Deviations From Plan

None.

## Follow-Ups

Manual device validation is still useful: remove books from a completed saved source, refresh/reopen the source, and confirm the removals persist.
