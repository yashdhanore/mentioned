# Test Agent Guide

`tests/` contains pytest coverage for the backend and extraction behavior.

## Patterns

- Place tests in `tests/test_*.py` or the relevant feature subdirectory with functions named `test_*`.
- Prefer `tmp_path`, `monkeypatch`, and in-process fakes for file, provider, and subprocess behavior so tests stay deterministic and offline.
- For provider integrations, cover both the configured-provider path and the fallback path.
- Keep tests focused on the behavior changed; broaden coverage when shared contracts, queues, auth, storage, or extraction output shape changes.

## Commands

- Run all backend tests with `pytest`.
- Run focused suites with paths such as `pytest tests/sources`, `pytest tests/extraction`, or `pytest tests/auth`.
- Update this guide when test layout, required fixtures, offline strategy, or validation commands change.
