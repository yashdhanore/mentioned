---
name: mobile-app
description: Use when changing the Expo React Native mobile app, mobile screens, Supabase auth, API integration, push notification behavior, design tokens, or mobile validation.
---

# Mobile App

Use this skill for work under `mobile/` and any backend contract it depends on.
For general Expo and React Native conventions, prefer the Expo plugin skills and
then apply this repo's project-specific guidance:

- Use `Expo:building-native-ui` / `@expo` for Expo UI, navigation, routes,
  responsive layout, native controls, and app-running guidance.
- Use `Expo:native-data-fetching` for API requests, authentication/token handling,
  network errors, caching, and offline behavior.

This skill should cover what the Expo plugin cannot know: Mentioned's backend
contracts, Supabase/Auth assumptions, push endpoints, design tokens, and local
validation commands.

## First Reads

- Mobile setup: `mobile/README.md`, `mobile/package.json`
- Expo config: `mobile/app.json`, `mobile/eas.json`
- App entry: `mobile/App.tsx`, `mobile/index.ts`
- Design tokens: `mobile/src/design-tokens.json`
- Backend contract: root `README.md`, `src/jobs/router.py`, `src/mentions/router.py`,
  `src/push/router.py`

Use `rg --files mobile | rg -v 'node_modules|dist|\\.expo'` to inspect app files.

## Workflow

1. For UI/navigation changes, apply `Expo:building-native-ui` first. For API,
   Supabase auth, or request/response handling, apply `Expo:native-data-fetching`
   first.
2. Identify the mobile flow: signed-out auth, job submission, job polling, mentions,
   corrections, delete, push notifications, or visual styling.
3. Check backend API response shapes before changing mobile assumptions.
4. Keep Supabase Auth behavior aligned with production. Do not hardcode tokens or
   service-role credentials.
5. Keep environment-specific URLs and keys out of committed code. Use documented
   Expo/mobile config patterns already present in the app.
6. Preserve mobile ergonomics: loading, empty, error, retry, and signed-out states.
7. If a backend contract change is needed, update backend tests and mobile code
   together.

## Validation

Inspect `mobile/package.json` before inventing commands. Current useful command:

```bash
cd mobile && npm run typecheck
```

For runtime checks, use Expo scripts from `mobile/package.json`:

```bash
cd mobile && npm run ios
cd mobile && npm run android
cd mobile && npm run web
```

Only run simulator/device flows when the user asks or the task requires it.

## Common Risks

- Backend response shape drift
- Auth assumptions that work locally but fail with Supabase Auth
- Push token registration without backend persistence checks
- Committing generated Expo output, `.expo`, `dist`, or `node_modules`
