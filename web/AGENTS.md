# Web Agent Guide

`web/` is the Astro web surface for the project.

## Commands

- Install dependencies from `web/` with `npm install`.
- Start development with `npm run dev`.
- Run the full web check with `npm test`.
- Useful focused checks: `npm run verify:content`, `npm run typecheck`, `npm run build`, and `npm run test:e2e`.

## Implementation Notes

- Keep page, component, public asset, and script changes inside `web/` unless shared project configuration is intentionally changing.
- Match the existing Astro, TypeScript, Playwright, and content verification patterns.
- Verify visual or interaction changes with Playwright screenshots or e2e coverage when behavior is user-facing.
- Do not commit `web/dist`, `web/test-results`, caches, dependency folders, or local environment files.
- Update this guide when web commands, package scripts, app structure, build outputs, or validation workflow changes.
