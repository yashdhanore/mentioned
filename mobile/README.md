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
redirect URLs in the Supabase Auth provider configuration.
Production mobile builds reject local or non-HTTPS Supabase URLs, Supabase secret/service-role
keys, local or non-HTTPS privacy policy URLs, `EXPO_PUBLIC_DEV_USER_ID`, and
`EXPO_PUBLIC_AUTH_REDIRECT_URL`. Use `EXPO_PUBLIC_AUTH_REDIRECT_URL` only for development sessions
such as Expo Go or tunnel testing.

Native iOS builds and development builds use `mentioned://auth/callback` for Supabase OAuth. Expo Go
uses an `exp://.../--/auth/callback` URL instead; if Safari says it cannot connect to the server
after provider sign-in, run Expo with a reachable host such as `npx expo start --tunnel` and add the
exact `[auth] OAuth redirect URL: ...` value printed in the Metro logs to Supabase Auth's allowed
redirect URLs. You can also force a callback URL for a dev session:

```bash
EXPO_PUBLIC_AUTH_REDIRECT_URL=exp://<reachable-host>:8081/--/auth/callback npm run ios
```

When testing on a physical iPhone against a local backend, set `EXPO_PUBLIC_API_BASE_URL` to your
Mac's LAN URL instead of `127.0.0.1`, for example `http://192.168.1.25:8000`.

For the Render + Supabase backend deployment, set:

```bash
EXPO_PUBLIC_APP_ENV=production
EXPO_PUBLIC_API_BASE_URL=https://mentioned-api.onrender.com
EXPO_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<publishable-or-anon-key>
EXPO_PUBLIC_PRIVACY_POLICY_URL=https://...
EXPO_PUBLIC_EAS_PROJECT_ID=2ca4c235-717e-48a1-aee8-173bf247f1b0
```

Native iOS and Android builds work with the deployed backend over HTTPS. CORS only affects browser
clients such as Expo web.

For the Release 1 iOS EAS/TestFlight runbook, see
[`../docs/release-1-ios-eas-testflight.md`](../docs/release-1-ios-eas-testflight.md).

## Validate

```bash
npm run check:ios-release-config
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
the normal UI. The app includes an iOS share-extension path for supported shared URL/text payloads,
while release validation still needs an EAS/native iOS build.
