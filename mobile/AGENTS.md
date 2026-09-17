# Mobile Agent Guide

`mobile/` is the Expo React Native app for capture, auth, signed-in and signed-out browsing, shared-source handling, and Supabase-backed runtime configuration.

## Commands

- Install dependencies from `mobile/` with `npm install`.
- Start Expo with `npm run start`.
- Run platform builds with `npm run ios` or `npm run android`.
- Typecheck with `npm run typecheck`.
- Use the focused scripts in `mobile/package.json` for capture, share URL, pending shared source, and Supabase config checks.

## Implementation Notes

- Keep app code under `mobile/src/` and follow the existing component, screen, API, theme, and utility organization.
- Keep `mobile/App.tsx` as the composition shell; auth session, shared-source intake, notification routing, and capture state live under `mobile/src/features/`.
- Use TypeScript types at boundaries that cross API, auth, persistence, notifications, and share-extension flows.
- Prefer existing design tokens, shared UI components, and `lucide-react-native` icons before adding new visual primitives.
- Styles live next to the component or screen that uses them as a sibling `*.styles.ts` file (e.g. `src/components/sheets.styles.ts`); `mobile/src/styles.ts` only holds styles shared across multiple components/screens.
- Do not commit Expo caches, builds, dependency folders, local app secrets, or generated native artifacts unless the task explicitly requires tracked native changes.
- Update this guide when mobile commands, package scripts, native artifact policy, app structure, or design-system conventions change.
