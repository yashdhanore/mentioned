# Release 1 iOS EAS/TestFlight Runbook

This runbook keeps Release 1 focused on iOS installability, native capture, and the book extraction loop. It documents the local checks that can run without Apple credentials and the credential-gated EAS/TestFlight path that the release operator must run from an authenticated EAS account.

## Release 1 iOS identity

| Field | Value |
|---|---|
| App name | `Mentioned` |
| Expo slug | `mentioned` |
| URL scheme | `mentioned` |
| iOS bundle identifier | `com.yashd18.mentioned` |
| Share extension target | `MentionedShareExtension` |
| Share extension bundle identifier | `com.yashd18.mentioned.ShareExtension` |
| App group | `group.com.yashd18.mentioned` |
| Supabase native auth callback | `mentioned://auth/callback` |
| Version | `1.0.0` |
| Encryption export flag | `ITSAppUsesNonExemptEncryption=false` |
| Tablet support | `false` |
| App icon | `mobile/assets/icon.png` |
| Splash image | `mobile/assets/splash-icon.png` |
| EAS project ID | `2ca4c235-717e-48a1-aee8-173bf247f1b0` |

Run the local release-config check before every TestFlight build:

```bash
cd mobile
npm run check:ios-release-config
```

The check verifies the app identity, bundle ID, scheme, version, encryption flag, tablet setting, icon/splash paths, EAS iOS build profile shape, and resolved Expo share-extension metadata.

## Production environment

Production EAS builds must use public Expo values with non-local HTTPS endpoints:

```bash
EXPO_PUBLIC_APP_ENV=production
EXPO_PUBLIC_API_BASE_URL=https://...
EXPO_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<publishable-key>
EXPO_PUBLIC_PRIVACY_POLICY_URL=https://...
EXPO_PUBLIC_EAS_PROJECT_ID=2ca4c235-717e-48a1-aee8-173bf247f1b0
```

These values must not be present in production builds:

| Value | Reason |
|---|---|
| `EXPO_PUBLIC_AUTH_REDIRECT_URL` | Development-only override for Expo Go or tunnel callback testing. Native production OAuth uses `mentioned://auth/callback`. |
| `EXPO_PUBLIC_DEV_USER_ID` | Local-only bypass. Production requests must use Supabase Auth. |
| Supabase service-role or `sb_secret_...` keys | Public mobile clients must only receive publishable/anon keys. |
| Local or non-HTTPS API, Supabase, or privacy policy URLs | Runtime startup guards reject these in production builds. |

The mobile runtime currently enforces the production API URL, privacy policy URL, Supabase URL/key, unsafe Supabase key, auth redirect override, and dev user ID requirements.

## EAS credential setup

These commands are local/account checks. They require an authenticated EAS account and, for credentials, Apple Developer access:

```bash
cd mobile
npx eas-cli@latest whoami
npx eas-cli@latest credentials -p ios
npx eas-cli@latest build:version:get -p ios
```

Use `credentials -p ios` to confirm the Apple team, bundle identifier, app group entitlement, provisioning profiles, distribution certificate, and App Store Connect connection before attempting a production binary.

The repository intentionally does not commit Apple IDs, App Store Connect API key files, issuer IDs, key IDs, passwords, reviewer account passwords, or `.env` files.

## Build and TestFlight commands

Local validation that does not upload a binary:

```bash
cd mobile
npm run check:ios-release-config
npm run test:supabase-config
npm run typecheck
```

Credential-gated EAS build and submit path:

```bash
cd mobile
npx eas-cli@latest build -p ios --profile development
npx eas-cli@latest build -p ios --profile preview
npx eas-cli@latest build -p ios --profile production
npx eas-cli@latest submit -p ios --latest --profile production
```

Use the production build for App Store Connect upload. After upload, run an internal TestFlight smoke test first. Add external beta testers only if the internal smoke passes, then submit the same Release 1 scope for App Store review.

This issue does not add Android release scope. Do not run Google Play submissions or add Android release metadata as part of this runbook.

## App Store Connect metadata worksheet

| Field | Release 1 value |
|---|---|
| App title | `Mentioned` |
| Subtitle draft | `Books from saved Reels` |
| Primary category | Owner decision required. Consider `Lifestyle` if the positioning is personal discovery, or `Books` if Apple accepts the core value as book tracking/discovery. |
| Privacy policy URL | Fill with the same HTTPS URL used for `EXPO_PUBLIC_PRIVACY_POLICY_URL`. |
| Support URL | Owner decision required. Use a stable HTTPS support page or contact route. |
| Screenshots | Capture signed-out, home with saved sources, paste-link sheet, processing detail, extracted books, no-books/failed state, and correction controls. |
| Demo account | Required if the app needs sign-in for review. Add credentials only in App Store Connect reviewer fields. |
| Review contact | Owner name, phone, and email required in App Store Connect. Do not store private contact details in the repository. |

## Reviewer notes draft

Use this as a starting point in App Store Connect, replacing placeholders with the final demo account and support details:

```text
Mentioned saves public Instagram Reel/post sources that mention books and turns them into a list of extracted books.

To test native capture on iOS:
1. Open a public Instagram Reel or post URL that mentions books.
2. Share the URL or text payload to Mentioned from the iOS share sheet.
3. Tap "Open Mentioned".
4. Sign in with the demo account if prompted.
5. Save the source and wait for the app to process it into extracted books.

Paste-link capture remains available inside the app if the share sheet is not convenient for review. Processing can take some time. Failed and no-books results are expected recoverable outcomes when the shared source cannot be processed or no books are found. Correction controls allow removing books that were extracted incorrectly.

Demo account:
Email: <provide in App Store Connect>
Password: <provide in App Store Connect>

Support: <support URL or contact>
```

Do not include real reviewer passwords in this repository. Add them only to the secure App Store Connect review information fields.

## Manual validation status

Live EAS preview, production, and TestFlight submission validation are blocked until the release operator has Apple Developer/App Store Connect access configured for the EAS project and bundle identifier. Record the EAS build URLs and App Store Connect submission status in the release issue or PR once those credential-gated commands run.
