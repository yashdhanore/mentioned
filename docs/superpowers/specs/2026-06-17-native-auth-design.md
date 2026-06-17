# Native Sign in with Apple + Google (remove supabase.co URL)

- **Date**: 2026-06-17
- **Status**: Approved (pending spec review)
- **Area**: `mobile/` (Expo React Native)
- **Driver**: App Store rejection, Guideline 2.1(a) — Performance — App Completeness

## Problem

The first App Store submission (v1.0 build 5) was rejected under Guideline
2.1(a): "the name contains placeholder content." The app's binary name is clean
(`mobile/app.json` → `"name": "Mentioned"`). The actual placeholder the reviewer
saw is the raw Supabase project host shown during sign-in.

The current auth flow is **web-OAuth only**. `signInWithProvider`
(`mobile/src/supabase.ts:82`) calls `supabase.auth.signInWithOAuth` and opens an
in-app browser via `expo-web-browser` to
`https://<project-ref>.supabase.co/auth/v1/authorize?...`. iOS renders a consent
sheet naming that random-looking `<project-ref>.supabase.co` host, which reads as
unfinished/placeholder content.

A community thread (r/Supabase, "is there any way to not show the supabase.co
URL") confirms both the cause and the free fix: paid options (Supabase custom
auth domain / vanity URL) require Pro, but obtaining the provider ID token
**natively on device** and exchanging it via `supabase.auth.signInWithIdToken`
removes the browser — and therefore the URL — entirely. The same move also
satisfies Apple Guideline 4.8 (native Sign in with Apple required when an app
offers third-party social login) and lets us adopt the official, store-compliant
native button components.

## Goal

Convert both the Apple and Google sign-in buttons from the web-OAuth redirect
flow to native on-device ID-token flows, so that:

1. No `*.supabase.co` URL or in-app browser appears during sign-in.
2. The app uses Apple's and Google's official native button components (correct
   logos and branding — fixes the missing Apple logo and the fake "G").
3. A Liquid-Glass-inspired aesthetic is applied to the surrounding auth chrome
   (not the buttons), honoring the `swiftui-liquid-glass` skill's intent within
   React Native's toolkit.

## Non-Goals

- No backend changes. `signInWithIdToken` yields a Supabase-issued session JWT
  with the same issuer/audience/`sub` as today (`src/auth/supabase.py:18`), so
  the API's token validation is unaffected.
- No Supabase custom auth domain / Pro upgrade.
- No literal SwiftUI Liquid Glass APIs — the app has no SwiftUI view layer. The
  `swiftui-liquid-glass` skill's native modifiers (`glassEffect`,
  `GlassEffectContainer`, `.buttonStyle(.glass)`) do not exist in React Native;
  we apply the skill's *principles* (availability gating + fallback) instead.

## Architecture

### 1. `mobile/src/supabase.ts` — native token flows

Replace the single web-OAuth `signInWithProvider` with two native functions.
Keep the `supabase` client and `currentAccessToken` unchanged. Remove
`expo-web-browser` from the auth path.

- **`signInWithApple()`**
  - Generate a random raw nonce; pass its SHA-256 hash to Apple, the raw nonce to
    Supabase (replay protection).
  - `AppleAuthentication.signInAsync({ requestedScopes: [FULL_NAME, EMAIL], nonce: hashedNonce })`.
  - `supabase.auth.signInWithIdToken({ provider: 'apple', token: credential.identityToken, nonce: rawNonce })`.
- **`signInWithGoogle()`**
  - `@react-native-google-signin/google-signin`: `GoogleSignin.configure({ webClientId, iosClientId })` once at module load, then `GoogleSignin.hasPlayServices()` + `GoogleSignin.signIn()`.
  - `supabase.auth.signInWithIdToken({ provider: 'google', token: idToken })`.

`webClientId` must be the Google **Web** OAuth client ID (the audience Supabase's
Google provider is configured with), not the iOS client ID.

### 2. `mobile/App.tsx` — dispatch

`handleSignIn` (`App.tsx:485`) dispatches per provider to the matching native
function. Existing `authProviderInFlight` loading state, error state, and the
`SignedOutScreen` prop wiring are preserved.

### 3. `mobile/src/screens/signed-out-screen.tsx` — native buttons + glass chrome

- Replace the custom `AppleSignInButton` `Pressable` with
  `AppleAuthentication.AppleAuthenticationButton`
  (`buttonType=SIGN_IN`, `buttonStyle=BLACK`, cornerRadius matched to layout).
- Replace the custom `GoogleSignInButton` `Pressable` with `GoogleSigninButton`.
- Native buttons are **not** restyled (HIG / Google brand compliance). In-flight
  state is conveyed by disabling the buttons and showing a lightweight overlay /
  the existing activity affordance, since the native Apple button exposes no
  custom label.
- Keep the `authProviderGroup` wrapper for layout/spacing.

### 4. Liquid Glass treatment (Option A — non-button chrome only)

- Add `expo-blur`.
- Apply a `<BlurView>` glass surface to the **`authPendingRow`** card (the
  "1 post ready to save" pending-share row; styles at `styles.ts:191`) and
  optionally the footer.
- Honor `swiftui-liquid-glass` principles in RN terms:
  - **Availability gating**: on iOS 26+, richer glass tint; on older iOS /
    Android, fall back to the current bordered surface (the existing
    `authPendingRow` border styling) — analogous to the skill's
    `#available(iOS 26, *)` + `.ultraThinMaterial` fallback.
  - **Consistency**: shared corner radius and spacing via existing `spacing`
    design tokens.
- The auth buttons are explicitly excluded from any glass treatment.

### 5. `mobile/app.json` — native config

- Add the `expo-apple-authentication` config plugin and `ios.usesAppleSignIn: true`.
- Add the `@react-native-google-signin/google-signin` config plugin with the iOS
  URL scheme (reversed iOS client ID).
- Add `expo-blur`.
- Bump `ios.buildNumber` (currently `5`) for resubmission.

### 6. Config / env

Google client IDs surfaced as `EXPO_PUBLIC_*` vars in `mobile/eas.json` (preview
+ production), consistent with existing Supabase env patterns. No secrets
committed; no service-role keys.

## Error & Cancel Handling

Preserve today's UX (current flow swallows cancel at `supabase.ts:98` and surfaces
real failures via `InlineMessage`).

- **Cancel** → silent no-op (clear in-flight, no error banner):
  - Apple: error code `ERR_REQUEST_CANCELED`.
  - Google: `statusCodes.SIGN_IN_CANCELLED`.
- **Real failure** → surface via the existing `InlineMessage` error path:
  - Missing `identityToken` / `idToken` from the provider.
  - `signInWithIdToken` returns an error.
  - Google Play Services unavailable (`hasPlayServices` throws).

## Testing & Validation

- `cd mobile && npm run typecheck`.
- New native modules require a **new EAS dev build** (not Expo Go). Per project
  release ritual: bump `ios.buildNumber`, build with `EXPO_NO_CAPABILITY_SYNC=1`.
- Enable the **Sign In with Apple** capability for the App ID.
- Manual on-device checks:
  - Apple sign-in with a real Apple ID completes and reaches the signed-in state.
  - Google sign-in completes and reaches the signed-in state.
  - Cancel paths for both produce no error banner.
  - **No `supabase.co` URL or in-app browser appears at any point.**
  - An authenticated API request still succeeds (confirms the session JWT shape
    is unchanged and the backend needs no edits).

## Risks

- **Google Web vs iOS client ID confusion** — using the wrong `webClientId`
  causes `signInWithIdToken` audience mismatch. Documented explicitly above.
- **Apple nonce mismatch** — must hash for Apple, send raw to Supabase.
- **Dev-build requirement** — native modules mean Expo Go can no longer run the
  auth flow; contributors need a dev client.
