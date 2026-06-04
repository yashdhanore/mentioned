# Implementation Report: Fix Pending Shared-Source Hardening

**GitHub Issue**: N/A

## Summary

Hardened the mobile pending shared-source flow. Supported Instagram source URLs now canonicalize to query/hash-free source keys before storage or dedupe, pending storage can compare before clearing, App deep-link handling uses source keys and processes launch URLs once, and production Supabase mobile config rejects unsafe URL/key/redirect values.

## Tasks Completed

| Task | Status | Notes |
|------|--------|-------|
| Harden shared-source URL canonicalization | Complete | Strips all query params and hashes from supported Instagram Reel/post URLs and rejects nested unsupported paths. |
| Make pending store canonical and race-aware | Complete | Persists canonical `sourceUrl`, `sourceKey`, and `createdAtMs`; invalid/corrupt records are removed; `clearIfCurrent` prevents stale clears. |
| Add Supabase mobile config guards | Complete | Added pure runtime config validator and script tests for production Supabase URL, public key, and redirect override checks. |
| Fix App deep-link dedupe and race handling | Complete | Uses `sourceKey` for incoming/restored/submitting/handled paths, guards stale submit/discard callbacks, and removes duplicate signed-out auth-error copy. |
| Document production mobile auth guards | Complete | README now documents Supabase secret/service-role key and redirect override rejection in production builds. |

## Validation

| Command | Result |
|---------|--------|
| `cd mobile && npm run test:share-url` | Passed |
| `cd mobile && npm run test:pending-shared-source` | Passed |
| `cd mobile && npm run test:supabase-config` | Passed |
| `cd mobile && npm run typecheck` | Passed |
| `python -m pytest tests/test_mobile_signed_out_screen.py` | Passed |
| `rg -n "secret/service-role|EXPO_PUBLIC_AUTH_REDIRECT_URL" mobile/README.md` | Passed |
| `python -m pytest` | Passed: 85 passed, 4 skipped |

## Files Changed

| File | Purpose |
|------|---------|
| `mobile/src/utils/shared-source-url.ts` | Canonical source key helper, stricter path validation, query/hash stripping. |
| `mobile/scripts/test-share-url-extraction.ts` | Regression coverage for token-like params, canonical keys, wrapped links, and unsupported paths. |
| `mobile/src/features/captures/pending-shared-source.ts` | Canonical pending records and compare-before-clear storage API. |
| `mobile/scripts/test-pending-shared-source.ts` | Regression coverage for canonical records, corrupt cleanup, and stale clear behavior. |
| `mobile/src/supabase-runtime-config.ts` | Pure production mobile Supabase config validation helpers. |
| `mobile/scripts/test-supabase-config.ts` | Script tests for unsafe Supabase mobile config values. |
| `mobile/src/supabase.ts` | Wires runtime config validation into Supabase client setup. |
| `mobile/package.json` | Adds `test:supabase-config`. |
| `mobile/App.tsx` | Source-key dedupe, one-time launch URL processing, and stale-safe pending submit/discard handling. |
| `tests/test_mobile_signed_out_screen.py` | Source-level regression checks for hardened pending intake. |
| `mobile/README.md` | Documents production mobile Supabase guard behavior. |

## Deviations From Plan

Manual iOS smoke testing was not run. Backend `/v1/jobs` idempotency remained out of scope as planned.

## Follow-Ups

Consider a separate backend idempotency plan if the product needs server-side at-least-once share submission protection.
