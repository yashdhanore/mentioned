# Implementation Report: Issue 20 iOS EAS/TestFlight Release Configuration

**GitHub Issue**: #20

## Summary

Added a repeatable iOS release-config check, documented the Release 1 EAS/TestFlight runbook, and updated the mobile README so production iOS release requirements are visible before building. No Android release scope, Apple credentials, `.env` files, or generated EAS/native artifacts were added.

## Tasks Completed

| Task | Status | Notes |
|------|--------|-------|
| Add repeatable iOS release config validation | Completed | Added `mobile/scripts/check-ios-release-config.ts` and `npm run check:ios-release-config`. |
| Create iOS EAS/TestFlight release runbook | Completed | Added identity snapshot, production env matrix, EAS commands, TestFlight sequence, and no-Android scope note. |
| Add App Store Connect metadata and reviewer notes draft | Completed | Added worksheet and reviewer notes placeholders without passwords or private contact details. |
| Clean up mobile README release guidance | Completed | Linked the runbook, added privacy policy/EAS project env values, and replaced stale share-extension wording. |
| Decide whether `mobile/eas.json` needs iOS submit metadata | Completed | Left `submit.production.ios` unchanged because no real App Store Connect identifiers were available in project context. |
| Run local validation | Completed | All local validation commands passed. |
| Record credential-gated manual validation | Completed | Runbook and this report state live EAS/TestFlight validation requires Apple Developer/App Store Connect access. |

## Validation

| Command | Result |
|---------|--------|
| `cd mobile && npm run check:ios-release-config` | Passed |
| `cd mobile && npm run test:supabase-config` | Passed |
| `cd mobile && npm run typecheck` | Passed |
| `git diff --check` | Passed |

Credential-gated commands were not run:

| Command | Result |
|---------|--------|
| `cd mobile && npx eas-cli@latest build -p ios --profile preview` | Not run; requires Apple Developer/App Store Connect credentials. |
| `cd mobile && npx eas-cli@latest build -p ios --profile production` | Not run; requires Apple Developer/App Store Connect credentials. |
| `cd mobile && npx eas-cli@latest submit -p ios --latest --profile production` | Not run; requires App Store Connect app/submission credentials. |

## Files Changed

| File | Purpose |
|------|---------|
| `docs/release-1-ios-eas-testflight.md` | New Release 1 iOS EAS/TestFlight runbook with config, env, build, metadata, reviewer notes, and manual validation status. |
| `mobile/scripts/check-ios-release-config.ts` | New local assertion script for iOS app identity, EAS profile shape, assets, and resolved share-extension metadata. |
| `mobile/package.json` | Added `check:ios-release-config` script. |
| `mobile/README.md` | Updated production env guidance and linked the release runbook. |

## Deviations From Plan

None. `mobile/eas.json` was intentionally left unchanged because no safe real iOS submit metadata was present.

## Follow-Ups

- Release operator must configure Apple Developer/App Store Connect credentials in EAS, run a production build, submit the latest build to TestFlight, and record EAS/App Store Connect build URLs in issue #20 or the release PR.
- Fill final App Store Connect privacy policy URL, support URL, review contact, screenshots, and demo account details outside the repository.
