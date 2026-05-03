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
