# Mentioned Mobile

React Native/Expo prototype for the user-facing Mentioned app.

The design source of truth is the repository root `DESIGN.md`. The exported DTCG token snapshot is
kept at `src/design-tokens.json`, and the React Native theme used by the app is in `src/theme.ts`.

## Run

```bash
npm install
npm run ios
```

Use `npm start` when you want the Expo QR/dev-server flow instead.

The app talks to the local FastAPI backend by default:

```bash
EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm run ios
```

Configure Supabase Auth before using the signed-in app flow:

```bash
EXPO_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co \
EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<publishable-key> \
EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 \
npm run ios
```

The mobile client persists the Supabase session locally and sends the session access token as
`Authorization: Bearer <token>` to the FastAPI backend. Production builds should set
`EXPO_PUBLIC_APP_ENV=production`; startup then fails if the API URL is local/non-HTTPS or Supabase
auth variables are missing. Add the app callback URL, `mentioned://auth/callback`, to the allowed
redirect URLs in the Supabase Auth provider configuration. When testing through Expo Go or a tunnel,
also add the callback URL printed by Expo for that session.

For the Render + Supabase backend deployment, set:

```bash
EXPO_PUBLIC_APP_ENV=production
EXPO_PUBLIC_API_BASE_URL=https://mentioned-api.onrender.com
EXPO_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<publishable-or-anon-key>
```

Native iOS and Android builds work with the deployed backend over HTTPS. CORS only affects browser
clients such as Expo web.

## Validate

```bash
npm run typecheck
```

## Scope

This prototype implements the v1 user-facing flow:

- Signed-out screen.
- Saved Reels home grid.
- Secondary paste-link sheet.
- Reel detail with `Finding books...`.
- Reel detail with read-only books mentioned.
- No-books and failed states.
- Profile/settings bottom sheet.

It intentionally does not expose confidence, evidence, jobs, stages, artifacts, or worker state in
the normal UI. Native iOS share extension work is a separate iOS integration step.
