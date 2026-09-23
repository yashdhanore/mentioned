# Test Agent Guide

`tests/` contains pytest coverage for the backend and extraction behavior.

## Patterns

- Follow the root [Testing](../AGENTS.md#testing) policy: E2E tests first, isolation tests only after listing the ways the system can fail.
- E2E tests live in `tests/e2e/`, run against the real local stack from `make dev` (Supabase Auth, Postgres with the `mentioned_api` role, API processes they boot themselves), and skip when that stack is not running.
  Fake external providers at the network boundary, such as a local Gemini server reached through the SDK's `GOOGLE_GEMINI_BASE_URL`, and stub only what cannot run locally, such as the Instagram download; never contact Instagram from a test.
  Shared plumbing (report, local stack discovery, API processes) lives in `tests/e2e/harness.py`.
  Each suite writes a JSON report of every check plus the API logs to `outputs/e2e/<suite>/<run>/`, with a copy of the newest report at `outputs/e2e/<suite>/latest.json`.
- Place tests in `tests/test_*.py` or the relevant feature subdirectory with functions named `test_*`.
- In isolation tests, prefer `tmp_path`, `monkeypatch`, and in-process fakes for file, provider, and subprocess behavior so tests stay deterministic and offline.
- For provider integrations, cover both the configured-provider path and the fallback path.
- Keep tests focused on the behavior changed; broaden coverage when shared contracts, queues, auth, storage, or extraction output shape changes.

## Commands

- Run all backend tests with `pytest`; the E2E suites run too when `make dev` is up.
- Run only the E2E suites with `pytest tests/e2e -v`.
- CI runs them in the `e2e` job with `E2E_REQUIRED=1`, which fails the run instead of skipping when the stack is missing; download a run's reports from the job's `e2e-reports` artifact.
- Run focused suites with paths such as `pytest tests/sources`, `pytest tests/extraction`, or `pytest tests/auth`.
- Update this guide when test layout, required fixtures, offline strategy, or validation commands change.
