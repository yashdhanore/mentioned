# Web Agent Guide

`web/` is the Astro web surface for the project.

## Commands

- Install dependencies from `web/` with `npm install`.
- Start development with `npm run dev`.
- Run the full web check with `npm test` (typecheck, build, then Playwright e2e).
- Useful focused checks: `npm run typecheck`, `npm run build`, and `npm run test:e2e`.
- Node version is pinned in `web/.nvmrc`; use the same version locally and in CI.
- No ESLint config here yet: `eslint-plugin-astro` requires ESLint 10, one major ahead of the ESLint 9 that `mobile/` uses.
  Rely on `npm run typecheck` (`astro check`) for now.

## Implementation Notes

- Fonts are self-hosted variable fonts from npm (`@fontsource-variable/plus-jakarta-sans` for display, `@fontsource-variable/geist` for body), imported in `BaseLayout.astro`; no external font `<link>`, to keep the site free of third-party requests.
  Only add a font family here if it is OFL-licensed and ships a variable-font npm package; keep `--font-display`/`--font-body` in `global.css` as the only two font stacks, and keep weights within what those fonts' variable axes actually support (Plus Jakarta Sans tops out at 800).
- Keep page, component, public asset, and script changes inside `web/` unless shared project configuration is intentionally changing.
- Match the existing Astro, TypeScript, Playwright, and content verification patterns.
- Verify visual or interaction changes with Playwright screenshots or e2e coverage when behavior is user-facing.
- Do not commit `web/dist`, `web/test-results`, caches, dependency folders, or local environment files.
- Update this guide when web commands, package scripts, app structure, build outputs, or validation workflow changes.
