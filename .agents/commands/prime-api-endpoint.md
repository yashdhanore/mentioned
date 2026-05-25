# Prime API Endpoint

Load focused context for adding or changing FastAPI endpoints.

## Input

Use the user's message after invoking this command as the endpoint, API behavior,
schema change, or bug to prime around. If blank, build general API endpoint context.

## Process

1. Read `AGENTS.md`, `README.md`, and relevant docs.
2. Inspect the app entrypoint and route registration:
   - `src/main.py`
3. Inspect the feature area related to the requested endpoint:
   - `src/jobs/`
   - `src/mentions/`
   - `src/books/`
   - `src/push/`
   - `src/auth/`
4. For the selected feature, map:
   - router
   - schemas
   - service
   - models
   - dependencies
   - exceptions
   - queue behavior if applicable
5. Inspect database/session behavior:
   - `src/database.py`
   - migrations under `migrations/`
   - Supabase/RLS docs when authorization or production data access changes
6. Inspect matching tests:
   - `tests/jobs/`
   - `tests/mentions/`
   - `tests/auth/`
   - relevant root tests
7. Identify response shape, auth mode behavior, status codes, and error handling
   conventions to preserve.

## Output

Summarize:

- Endpoint behavior requested
- Existing route/service/schema pattern to follow
- Auth and DB/session considerations
- Tests to add or update
- Migration/Supabase implications, if any
- Validation commands to use next

Default validation:

```bash
python -m pytest tests
```

Use targeted tests first when the scope is narrow.
