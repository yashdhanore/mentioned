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

For local visual inspection without Supabase OAuth, run the backend with `AUTH_MODE=dev` and start
Expo with dev auth enabled. The mobile app will skip Supabase session restoration and send
`Authorization: Bearer dev:<user-id>` to the API:

```bash
EXPO_PUBLIC_AUTH_MODE=dev \
EXPO_PUBLIC_DEV_USER_ID=00000000-0000-4000-8000-000000000001 \
EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 \
npm run web
```

`EXPO_PUBLIC_DEV_USER_ID` should match the backend `DEV_USER_ID` when you want to load seeded local
data. Production builds reject `EXPO_PUBLIC_AUTH_MODE=dev` and `EXPO_PUBLIC_DEV_USER_ID`.

If `mobile/.env` already sets `EXPO_PUBLIC_APP_ENV=production` (e.g. for native builds against the
deployed backend), shell-prefixing the command as shown above does **not** reliably override it:
Expo bakes `EXPO_PUBLIC_*` values into a build-time `expo/virtual/env` snapshot straight from the
`.env` files, which can win over already-set shell/process env depending on what else is cached.
The reliable way to override for local dev is a `mobile/.env.local` file (gitignored, takes
precedence over `.env`):

```
EXPO_PUBLIC_APP_ENV=development
EXPO_PUBLIC_AUTH_MODE=dev
EXPO_PUBLIC_DEV_USER_ID=00000000-0000-4000-8000-000000000001
EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

If env changes still don't seem to take effect after editing `.env`/`.env.local`, Metro's disk
transform cache (outside the project, under `$TMPDIR/metro-cache`) can serve stale inlined values
even across restarts; `npx expo start --clear` does not clear it. Wipe it manually and restart:

```bash
rm -rf "$TMPDIR/metro-cache" "$TMPDIR"/metro-file-map-*
npx expo start --web --clear
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
keys, and `EXPO_PUBLIC_AUTH_REDIRECT_URL`. Use `EXPO_PUBLIC_AUTH_REDIRECT_URL` only for
development sessions such as Expo Go or tunnel testing.

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
```

Native iOS and Android builds work with the deployed backend over HTTPS. CORS only affects browser
clients such as Expo web.

## Native Sign in with Apple + Google

Sign-in uses **native on-device ID-token flows** (`supabase.auth.signInWithIdToken`), not the web
OAuth redirect. No `*.supabase.co` URL or in-app browser appears during sign-in. These flows rely on
native modules, so they **require an EAS dev/release build — they do not work in Expo Go.**

### One-time setup checklist

- [ ] **Apple — enable the capability.** In the Apple Developer portal, enable **Sign In with Apple**
      for the App ID `com.yashd18.mentioned`. `app.json` includes the
      `expo-apple-authentication` config plugin; do not add `ios.usesAppleSignIn`, because the share
      extension must not receive the Apple sign-in entitlement. No client ID is needed for Apple.
- [ ] **Supabase — Apple provider.** Confirm the Apple provider is enabled in Supabase Auth (it
      already is for the existing flow; native sign-in reuses the same provider config).
- [ ] **Google — create OAuth client IDs** in Google Cloud Console → *APIs & Services → Credentials*
      for the project tied to Supabase's Google provider:
  - [ ] **Web** client ID (type *Web application*). This is the audience Supabase verifies against —
        it is the one passed to `GoogleSignin.configure({ webClientId })`, **not** the iOS client ID.
  - [ ] **iOS** client ID (type *iOS*, bundle ID `com.yashd18.mentioned`).
- [ ] **Supabase — Google provider.** Set the **Web** client ID (and secret) on Supabase Auth's
      Google provider so issued tokens validate. Add the iOS client ID to the provider's
      *Authorized Client IDs* list.
- [ ] **Verify the Google OAuth values**:
  - [ ] `app.json` → `@react-native-google-signin/google-signin` plugin → `iosUrlScheme`. This is the
        **reversed** iOS client ID, e.g. iOS client `123-abc.apps.googleusercontent.com` becomes
        `com.googleusercontent.apps.123-abc`.
  - [ ] `eas.json` → `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` (preview + production) → the **Web** client ID.
  - [ ] `eas.json` → `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID` (preview + production) → the **iOS** client ID.

### Build & on-device verification

- [ ] Bump `ios.buildNumber` in `app.json` (already at `6` for this change; bump again per release).
- [ ] Build a dev client: `EXPO_NO_CAPABILITY_SYNC=1 eas build --profile development --platform ios`.
- [ ] On device, confirm:
  - [ ] Apple sign-in completes and reaches the signed-in state.
  - [ ] Google sign-in completes and reaches the signed-in state.
  - [ ] Cancelling either sheet shows **no** error banner (silent no-op).
  - [ ] **No `supabase.co` URL or in-app browser appears at any point.**
  - [ ] An authenticated API request still succeeds (session JWT shape is unchanged; backend needs
        no edits).

> The legacy web-OAuth redirect (`mentioned://auth/callback`, `EXPO_PUBLIC_AUTH_REDIRECT_URL`) is no
> longer used by the production sign-in path. The `EXPO_PUBLIC_AUTH_REDIRECT_URL` guard remains only
> to keep it out of production builds.

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
