# Implementation Report: Fix iOS Book Cover Thumbnails

**GitHub Issue**: N/A

## Summary

Normalized Google Books HTTP cover image URLs to HTTPS before they reach persistence, and added a React Native image error fallback so book rows render the generated spine instead of a blank cover area when native image loading fails.

## Tasks Completed

| Task | Status | Notes |
|------|--------|-------|
| Add Google Books HTTP cover regression test | Complete | Added coverage for `http://books.google.com/books/content?...` returning as HTTPS. |
| Implement cover URL normalization | Complete | Added a parser helper that preserves valid HTTPS URLs, upgrades Google Books HTTP URLs, and drops unsupported values. |
| Add mobile cover load fallback | Complete | `BookRow` now switches to `BookSpine` on image load error and resets when the cover URL changes. |
| Confirm capture mapping preserves cover URLs | Complete | Added an assertion to the capture mapping script for `coverImageUrl`. |
| Run focused validation | Complete | Backend, worker, capture mapping, typecheck, and full pytest validation passed. |
| iOS simulator visual check | Not run | An Expo/iOS session was already running, so no duplicate simulator process was started from this turn. |

## Validation

| Command | Result |
|---------|--------|
| `python -m pytest tests/extraction/test_google_books.py::test_enrich_book_normalizes_google_books_cover_url_to_https -q` | Blocked initially: `python` was not on PATH. |
| `python3 -m pytest tests/extraction/test_google_books.py::test_enrich_book_normalizes_google_books_cover_url_to_https -q` | Blocked initially: pytest was not installed in the global Python. |
| `python3 -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"` | Passed; created ignored local test environment. |
| `.venv/bin/python -m pytest tests/extraction/test_google_books.py -q` | Passed: 5 passed. |
| `.venv/bin/python -m pytest tests/test_worker_books.py -q` | Passed: 3 passed, 19 warnings. |
| `npm run test:captures && npm run typecheck` | Passed. |
| `.venv/bin/python -m pytest` | Passed: 104 passed, 4 skipped, 121 warnings. |

## Files Changed

| File | Purpose |
|------|---------|
| `tests/extraction/test_google_books.py` | Regression coverage for Google Books HTTP cover URL normalization. |
| `src/extraction/google_books.py` | Cover URL normalization at Google Books parsing boundary. |
| `mobile/src/components/books.tsx` | Native image-load failure fallback to generated `BookSpine`. |
| `mobile/scripts/test-captures.ts` | Explicit assertion that API `cover_image_url` maps to mobile `coverImageUrl`. |

## Deviations From Plan

- Did not start a new `npm run ios` session because an Expo/iOS simulator session was already running in the workspace.
- `mobile/package.json` already had the `test:captures` script as an existing uncommitted change before this implementation.

## Follow-Ups

- Verify visually in the running iOS simulator that rows with failing native cover loads now show `BookSpine`.
- Existing persisted `http://books.google.com/...` rows still need a separate backfill if old data should be repaired.
