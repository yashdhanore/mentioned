# Prime Mobile

Load focused context for the mobile Expo app.

## Input

Use the user's message after invoking this command as the mobile screen, flow, bug,
API integration, auth behavior, or notification task to prime around. If blank,
build general mobile app context.

## Process

1. Read `AGENTS.md`, root `README.md`, and `mobile/README.md`.
2. Inspect mobile project configuration:
   - `mobile/package.json`
   - `mobile/app.json`
   - `mobile/eas.json`
   - `mobile/tsconfig.json`
   - `mobile/src/design-tokens.json`
3. Map relevant app code under `mobile/`:
   - navigation/routes
   - screens
   - API client or data access
   - Supabase auth usage
   - push notification registration/handling
   - shared components and styling conventions
4. Inspect backend contracts the mobile app depends on:
   - `POST /v1/saved-sources`
   - `GET /v1/saved-sources`
   - `GET /v1/saved-sources/{saved_source_id}`
   - `DELETE /v1/saved-sources/{saved_source_id}`
   - push token endpoints when relevant
5. Inspect mobile tests or scripts if present. If none exist, identify realistic
   verification steps.
6. Check whether a change also requires backend API, Supabase Auth, Render config,
   or environment updates.

## Output

Summarize:

- Mobile task understanding
- Relevant screens/components/files
- Backend contracts involved
- Auth and environment assumptions
- Tests or manual verification needed
- Risks or missing context

Prefer mobile-local commands from `mobile/package.json` when validating. Do not
invent package scripts; inspect the file first.
