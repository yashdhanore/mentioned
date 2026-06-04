# Fix Pending Shared-Source Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the Expo mobile pending shared-source flow so signed-out native shares do not retain token-like URL data, duplicate on auth changes, or lose/clear the wrong pending source during async races.

**Architecture:** Keep the backend job API unchanged for this pass and harden the mobile intake boundary. Canonicalize supported Instagram source URLs before storage or dedupe, use one source-derived key across raw deep links and restored records, process the launch URL once per app lifetime, and make pending-store clearing compare against the current stored source before removing it.

**Tech Stack:** Expo React Native, TypeScript, AsyncStorage, Supabase Auth, `tsx` script tests, pytest source regressions.

---

## Summary

The current pending shared-source implementation preserves signed-out shares, but review found several hardening gaps:

- URL normalization strips only `utm_*` and `igsh`, so token-like query params can persist.
- `Linking.getInitialURL()` is tied to a callback that changes with auth state, so cold-start links can be processed more than once.
- Dedupe keys mix raw deep-link URLs and stored-source keys.
- Pending restore, submit, and discard can race with newer incoming shares.
- App writes expected signed-out pending state into `authError`, duplicating the signed-out prompt.
- Production Supabase mobile config needs stricter guards around public keys and redirect overrides.

This plan fixes those mobile issues first. Backend `/v1/jobs` idempotency is explicitly out of scope for this implementation because it changes API contract, schema, migrations, quota semantics, and RLS verification.

## Scope

- In:
  - Canonical shared-source URL sanitization for supported Instagram Reel/post URLs.
  - Stable source-derived dedupe key used by incoming links, restored pending records, and submission guards.
  - Pending store compare-and-clear behavior.
  - One-time launch URL processing with live event-link handling.
  - Race-safe pending restore and async submit/discard callbacks.
  - Signed-out pending state represented by pending-source UI, not `authError`.
  - Production Supabase mobile config guard tests and implementation.
  - Mobile script tests, source-level pytest regression, and README note.
- Out:
  - Backend `/v1/jobs` idempotency.
  - Database schema or Supabase migration changes.
  - New `/v1/shared-sources` endpoint.
  - Android share-intent changes.
  - Extraction pipeline changes.

## Issue

- GitHub Issue: N/A for this hardening review.
- Related: Issue 15, preserve a shared source through sign-in.
- URL: N/A.

## Risk Level

Medium. The work is mobile-only, but it touches app startup/deep-link/auth coordination where regressions can duplicate submissions or strand a pending share.

## Patterns To Follow

| Area | Source | Pattern |
|------|--------|---------|
| Runtime config guards | `mobile/src/api.ts` | Validate production-only env constraints at module load with pure helper functions where possible. |
| Shared URL parser tests | `mobile/scripts/test-share-url-extraction.ts` | Use `node:assert/strict` and run through an npm `tsx` script. |
| Pending store tests | `mobile/scripts/test-pending-shared-source.ts` | Keep storage injectable with an in-memory fake for deterministic tests. |
| App coordinator | `mobile/App.tsx` | Keep App as coordinator for auth, deep links, pending prompt, and `submitSharedUrl`. |
| Mobile auth | `mobile/src/supabase.ts` | Use Supabase PKCE, AsyncStorage persistence, `detectSessionInUrl: false`, and the existing `AuthProvider` restriction. |
| Backend job creation | `src/jobs/router.py` and `src/jobs/service.py` | Current `POST /v1/jobs` always creates a new queued job, so idempotency needs a separate backend contract plan. |

## Files To Change

| File | Action | Purpose |
|------|--------|---------|
| `mobile/src/utils/shared-source-url.ts` | UPDATE | Strip all query/hash data from supported Instagram source URLs and export a canonical source key helper. |
| `mobile/scripts/test-share-url-extraction.ts` | UPDATE | Cover token-like query stripping, canonical dedupe identity, wrapped deep links, and invalid share links. |
| `mobile/src/features/captures/pending-shared-source.ts` | UPDATE | Store/load canonical source records, expose `sourceKey`, and add compare-and-clear. |
| `mobile/scripts/test-pending-shared-source.ts` | UPDATE | Cover canonical save/load, corrupt cleanup, and clear-if-current race behavior. |
| `mobile/src/supabase-runtime-config.ts` | CREATE | Hold pure Supabase mobile config validation helpers that are testable without creating a Supabase client. |
| `mobile/src/supabase.ts` | UPDATE | Use the config helpers and reject unsafe production Supabase public key or redirect override values. |
| `mobile/scripts/test-supabase-config.ts` | CREATE | Verify production config rejects secret/service-role keys, local/non-HTTPS Supabase URLs, and redirect overrides. |
| `mobile/package.json` | UPDATE | Add `test:supabase-config` script. |
| `mobile/App.tsx` | UPDATE | Apply stable source-key dedupe, one-time initial URL processing, race-safe pending state updates, and remove expected pending auth error writes. |
| `tests/test_mobile_signed_out_screen.py` | UPDATE | Add source-level regression checks for duplicate-copy removal, launch URL guard, and source-key compare clearing. |
| `mobile/README.md` | UPDATE | Document production mobile auth config guard behavior. |

## Task 1: Harden Shared-Source URL Canonicalization

**Files:**
- Modify: `mobile/scripts/test-share-url-extraction.ts`
- Modify: `mobile/src/utils/shared-source-url.ts`

- [ ] **Step 1: Write failing parser assertions**

  Add assertions that prove no query or hash survives canonicalization, including token-like params that currently survive:

  ```ts
  assert.equal(
    extractSharedSourceUrl({
      url: 'https://www.instagram.com/reel/SECRET/?utm_source=x&igsh=abc&access_token=secret&code=oauth&state=oauth#frag',
    }),
    'https://www.instagram.com/reel/SECRET/',
  );

  assert.equal(
    sharedUrlFromMentionedDeepLink(
      `mentioned://share?url=${encodeURIComponent(
        'https://www.instagram.com/p/PARAMS/?ref=feed&tracking=kept&fbclid=abc&token=secret',
      )}`,
    ),
    'https://www.instagram.com/p/PARAMS/',
  );

  assert.deepEqual(
    parseMentionedShareDeepLink(
      `mentioned://share?url=${encodeURIComponent(
        'https://www.instagram.com/reel/PARAMS/?ref=feed&utm_source=ig_web_copy_link&tracking=kept&igsh=removed',
      )}`,
    ),
    {
      type: 'valid',
      sourceUrl: 'https://www.instagram.com/reel/PARAMS/',
    },
  );
  ```

- [ ] **Step 2: Add stable source-key assertions**

  Import the new helper in the test file:

  ```ts
  import {
    canonicalSharedSourceKey,
    extractSharedSourceUrl,
    isSupportedSharedSourceUrl,
    parseMentionedShareDeepLink,
    sharedUrlFromMentionedDeepLink,
  } from '../src/utils/shared-source-url';
  ```

  Add assertions:

  ```ts
  assert.equal(
    canonicalSharedSourceKey('https://www.instagram.com/reel/DUP/?utm_source=one&token=secret'),
    'https://www.instagram.com/reel/DUP/',
  );

  assert.equal(
    canonicalSharedSourceKey('https://www.instagram.com/reel/DUP/?utm_source=two'),
    canonicalSharedSourceKey('https://www.instagram.com/reel/DUP/'),
  );

  assert.equal(canonicalSharedSourceKey('https://example.com/reel/DUP/'), null);
  ```

- [ ] **Step 3: Run parser test and verify failure**

  ```bash
  cd mobile && npm run test:share-url
  ```

  Expected: FAIL because `canonicalSharedSourceKey` does not exist and the existing parser preserves `ref` or `tracking`.

- [ ] **Step 4: Implement canonical URL behavior**

  Update `mobile/src/utils/shared-source-url.ts` so canonical source URLs clear all search params and hashes:

  ```ts
  function normalizeSharedSourceUrl(url: URL): string {
    const normalizedUrl = new URL(url.toString());
    normalizedUrl.hash = '';
    normalizedUrl.search = '';
    return normalizedUrl.toString();
  }

  export function canonicalSharedSourceKey(value: string): string | null {
    return supportedNormalizedUrl(value);
  }
  ```

  Keep host and HTTPS validation. Tighten path validation to recognize only Instagram Reel/post routes:

  ```ts
  function hasSupportedPath(pathname: string): boolean {
    const [, kind, shortcode] = pathname.split('/');
    return (kind === 'reel' || kind === 'p') && Boolean(shortcode);
  }
  ```

  This preserves existing `/reel/{id}/` and `/p/{id}/` inputs while rejecting unrelated paths that merely contain `/reel/` or `/p/` later in the path.

- [ ] **Step 5: Run parser test and verify pass**

  ```bash
  cd mobile && npm run test:share-url
  ```

  Expected: PASS with `share URL extraction tests passed`.

## Task 2: Make Pending Store Canonical And Race-Aware

**Files:**
- Modify: `mobile/scripts/test-pending-shared-source.ts`
- Modify: `mobile/src/features/captures/pending-shared-source.ts`

- [ ] **Step 1: Write failing pending-store assertions**

  Update the expected record to include `sourceKey`:

  ```ts
  const sourceUrl = 'https://www.instagram.com/reel/PENDING/?token=secret&utm_source=x';
  const canonicalUrl = 'https://www.instagram.com/reel/PENDING/';
  const record = createPendingSharedSource(sourceUrl, 1_800_000_000_000);

  assert.deepEqual(record, {
    sourceUrl: canonicalUrl,
    sourceKey: canonicalUrl,
    createdAtMs: 1_800_000_000_000,
  });
  ```

  Add compare-and-clear coverage:

  ```ts
  const first = await store.save('https://www.instagram.com/reel/FIRST/', 1);
  assert.equal(await store.clearIfCurrent('https://www.instagram.com/reel/OTHER/'), false);
  assert.deepEqual(await store.load(), first);
  assert.equal(await store.clearIfCurrent(first.sourceKey), true);
  assert.equal(await store.load(), null);

  const stale = await store.save('https://www.instagram.com/reel/STALE/', 2);
  const fresh = await store.save('https://www.instagram.com/reel/FRESH/', 3);
  assert.equal(await store.clearIfCurrent(stale.sourceKey), false);
  assert.deepEqual(await store.load(), fresh);
  ```

  Add invalid stored values with sensitive-looking fields:

  ```ts
  await storage.setItem(
    PENDING_SHARED_SOURCE_STORAGE_KEY,
    JSON.stringify({
      sourceUrl: 'https://example.com/reel/BAD/',
      access_token: 'secret',
      refresh_token: 'secret',
      createdAtMs: 1,
    }),
  );
  assert.equal(await store.load(), null);
  assert.equal(storage.values.has(PENDING_SHARED_SOURCE_STORAGE_KEY), false);
  ```

- [ ] **Step 2: Run pending-store test and verify failure**

  ```bash
  cd mobile && npm run test:pending-shared-source
  ```

  Expected: FAIL because `sourceKey` and `clearIfCurrent` do not exist.

- [ ] **Step 3: Implement canonical records and compare clearing**

  Update the helper import and type:

  ```ts
  import {
    canonicalSharedSourceKey,
    isSupportedSharedSourceUrl,
  } from '../../utils/shared-source-url';

  export type PendingSharedSource = {
    sourceUrl: string;
    sourceKey: string;
    createdAtMs: number;
  };
  ```

  Implement creation through canonicalization:

  ```ts
  export function createPendingSharedSource(
    sourceUrl: string,
    createdAtMs = Date.now(),
  ): PendingSharedSource {
    const sourceKey = canonicalSharedSourceKey(sourceUrl);
    if (!sourceKey) {
      throw new Error('Unsupported shared source URL.');
    }
    return {
      sourceUrl: sourceKey,
      sourceKey,
      createdAtMs,
    };
  }
  ```

  Parse persisted records by canonicalizing the stored `sourceUrl`; do not trust stored `sourceKey`:

  ```ts
  export function parsePendingSharedSource(rawValue: string | null): PendingSharedSource | null {
    if (!rawValue) {
      return null;
    }

    try {
      const parsed = JSON.parse(rawValue) as Partial<PendingSharedSource>;
      if (typeof parsed.sourceUrl !== 'string' || !isSupportedSharedSourceUrl(parsed.sourceUrl)) {
        return null;
      }
      if (typeof parsed.createdAtMs !== 'number' || !Number.isFinite(parsed.createdAtMs)) {
        return null;
      }
      return createPendingSharedSource(parsed.sourceUrl, parsed.createdAtMs);
    } catch {
      return null;
    }
  }
  ```

  Add compare-and-clear to the store by defining local functions before returning the store object:

  ```ts
  export function createPendingSharedSourceStore(storage: KeyValueStorage) {
    const load = async (): Promise<PendingSharedSource | null> => {
      const storedValue = await storage.getItem(PENDING_SHARED_SOURCE_STORAGE_KEY);
      const source = parsePendingSharedSource(storedValue);
      if (!source && storedValue) {
        await storage.removeItem(PENDING_SHARED_SOURCE_STORAGE_KEY);
      }
      return source;
    };

    const save = async (sourceUrl: string, createdAtMs = Date.now()): Promise<PendingSharedSource> => {
      const source = createPendingSharedSource(sourceUrl, createdAtMs);
      await storage.setItem(PENDING_SHARED_SOURCE_STORAGE_KEY, serializePendingSharedSource(source));
      return source;
    };

    const clear = async (): Promise<void> => {
      await storage.removeItem(PENDING_SHARED_SOURCE_STORAGE_KEY);
    };

    const clearIfCurrent = async (sourceKey: string): Promise<boolean> => {
      const current = await load();
      if (!current || current.sourceKey !== sourceKey) {
        return false;
      }
      await clear();
      return true;
    };

    return { load, save, clear, clearIfCurrent };
  }
  ```

- [ ] **Step 4: Run pending-store test and verify pass**

  ```bash
  cd mobile && npm run test:pending-shared-source
  ```

  Expected: PASS with `pending shared source tests passed`.

## Task 3: Add Pure Supabase Mobile Config Guards

**Files:**
- Create: `mobile/src/supabase-runtime-config.ts`
- Create: `mobile/scripts/test-supabase-config.ts`
- Modify: `mobile/package.json`
- Modify: `mobile/src/supabase.ts`

- [ ] **Step 1: Add script entry**

  Add this npm script:

  ```json
  "test:supabase-config": "tsx scripts/test-supabase-config.ts"
  ```

- [ ] **Step 2: Write failing config tests**

  Create `mobile/scripts/test-supabase-config.ts`:

  ```ts
  import assert from 'node:assert/strict';

  import {
    isUnsafeSupabasePublicKey,
    validateSupabaseMobileConfig,
  } from '../src/supabase-runtime-config';

  const anonPayload = Buffer.from(JSON.stringify({ role: 'anon' })).toString('base64url');
  const serviceRolePayload = Buffer.from(JSON.stringify({ role: 'service_role' })).toString('base64url');
  const legacyAnonJwt = `header.${anonPayload}.signature`;
  const legacyServiceRoleJwt = `header.${serviceRolePayload}.signature`;

  assert.equal(isUnsafeSupabasePublicKey('sb_publishable_abc'), false);
  assert.equal(isUnsafeSupabasePublicKey(legacyAnonJwt), false);
  assert.equal(isUnsafeSupabasePublicKey('sb_secret_abc'), true);
  assert.equal(isUnsafeSupabasePublicKey(legacyServiceRoleJwt), true);

  assert.doesNotThrow(() =>
    validateSupabaseMobileConfig({
      appEnv: 'production',
      supabaseUrl: 'https://project-ref.supabase.co',
      supabasePublishableKey: 'sb_publishable_abc',
      authRedirectUrlOverride: '',
    }),
  );

  assert.throws(() =>
    validateSupabaseMobileConfig({
      appEnv: 'production',
      supabaseUrl: 'http://127.0.0.1:54321',
      supabasePublishableKey: 'sb_publishable_abc',
      authRedirectUrlOverride: '',
    }),
  );

  assert.throws(() =>
    validateSupabaseMobileConfig({
      appEnv: 'production',
      supabaseUrl: 'https://project-ref.supabase.co',
      supabasePublishableKey: 'sb_secret_abc',
      authRedirectUrlOverride: '',
    }),
  );

  assert.throws(() =>
    validateSupabaseMobileConfig({
      appEnv: 'production',
      supabaseUrl: 'https://project-ref.supabase.co',
      supabasePublishableKey: legacyServiceRoleJwt,
      authRedirectUrlOverride: '',
    }),
  );

  assert.throws(() =>
    validateSupabaseMobileConfig({
      appEnv: 'production',
      supabaseUrl: 'https://project-ref.supabase.co',
      supabasePublishableKey: 'sb_publishable_abc',
      authRedirectUrlOverride: 'exp://localhost:8081/--/auth/callback',
    }),
  );

  assert.doesNotThrow(() =>
    validateSupabaseMobileConfig({
      appEnv: 'development',
      supabaseUrl: '',
      supabasePublishableKey: '',
      authRedirectUrlOverride: 'exp://localhost:8081/--/auth/callback',
    }),
  );

  console.log('supabase config tests passed');
  ```

- [ ] **Step 3: Run config test and verify failure**

  ```bash
  cd mobile && npm run test:supabase-config
  ```

  Expected: FAIL because `mobile/src/supabase-runtime-config.ts` does not exist.

- [ ] **Step 4: Implement pure config helpers**

  Create `mobile/src/supabase-runtime-config.ts`:

  ```ts
  export type SupabaseMobileRuntimeConfig = {
    appEnv?: string;
    supabaseUrl: string;
    supabasePublishableKey: string;
    authRedirectUrlOverride: string;
  };

  function isProductionBuild(appEnv?: string): boolean {
    return appEnv?.trim().toLowerCase() === 'production';
  }

  function isLocalHost(hostname: string): boolean {
    return ['localhost', '127.0.0.1', '0.0.0.0', '::1'].includes(hostname);
  }

  const BASE64_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';

  function decodeBase64Ascii(value: string): string | null {
    let buffer = 0;
    let bits = 0;
    let output = '';

    for (const char of value.replace(/=+$/, '')) {
      const index = BASE64_ALPHABET.indexOf(char);
      if (index < 0) {
        return null;
      }
      buffer = (buffer << 6) | index;
      bits += 6;
      if (bits >= 8) {
        bits -= 8;
        output += String.fromCharCode((buffer >> bits) & 0xff);
      }
    }

    return output;
  }

  function decodeBase64UrlJson(segment: string): Record<string, unknown> | null {
    try {
      const normalized = segment.replace(/-/g, '+').replace(/_/g, '/');
      const padded = normalized.padEnd(normalized.length + ((4 - (normalized.length % 4)) % 4), '=');
      const decoded = decodeBase64Ascii(padded);
      if (!decoded) {
        return null;
      }
      return JSON.parse(decoded) as Record<string, unknown>;
    } catch {
      return null;
    }
  }

  export function isUnsafeSupabasePublicKey(value: string): boolean {
    const key = value.trim();
    if (!key) {
      return false;
    }
    if (key.startsWith('sb_secret_')) {
      return true;
    }
    const jwtPayload = key.split('.')[1];
    const parsedPayload = jwtPayload ? decodeBase64UrlJson(jwtPayload) : null;
    return parsedPayload?.role === 'service_role';
  }

  export function validateSupabaseMobileConfig(config: SupabaseMobileRuntimeConfig): void {
    if (!isProductionBuild(config.appEnv)) {
      return;
    }
    if (!config.supabaseUrl || !config.supabasePublishableKey) {
      throw new Error('Production mobile builds require EXPO_PUBLIC_SUPABASE_URL and EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY.');
    }
    if (isUnsafeSupabasePublicKey(config.supabasePublishableKey)) {
      throw new Error('Production mobile builds must not expose a Supabase secret or service-role key.');
    }
    if (config.authRedirectUrlOverride.trim()) {
      throw new Error('Production mobile builds must not set EXPO_PUBLIC_AUTH_REDIRECT_URL.');
    }

    let parsedUrl: URL;
    try {
      parsedUrl = new URL(config.supabaseUrl);
    } catch {
      throw new Error('EXPO_PUBLIC_SUPABASE_URL must be a valid URL in production builds.');
    }
    if (parsedUrl.protocol !== 'https:' || isLocalHost(parsedUrl.hostname)) {
      throw new Error('Production mobile builds require a non-local HTTPS Supabase URL.');
    }
  }
  ```

- [ ] **Step 5: Wire helpers into Supabase client setup**

  In `mobile/src/supabase.ts`, import and call the helper after env values are read:

  ```ts
  import { validateSupabaseMobileConfig } from '@/supabase-runtime-config';
  ```

  Replace the current production-only missing-config check with:

  ```ts
  validateSupabaseMobileConfig({
    appEnv: process.env.EXPO_PUBLIC_APP_ENV,
    supabaseUrl,
    supabasePublishableKey,
    authRedirectUrlOverride,
  });
  ```

  Keep `isSupabaseConfigured` unchanged for development fallback.

- [ ] **Step 6: Run config test and typecheck**

  ```bash
  cd mobile && npm run test:supabase-config
  cd mobile && npm run typecheck
  ```

  Expected: PASS with `supabase config tests passed`; typecheck passes.

## Task 4: Fix App Deep-Link Dedupe And Race Handling

**Files:**
- Modify: `mobile/App.tsx`
- Modify: `tests/test_mobile_signed_out_screen.py`

- [ ] **Step 1: Add failing source-level regression checks**

  Extend `tests/test_mobile_signed_out_screen.py`:

  ```py
  def test_pending_shared_source_intake_is_hardened() -> None:
      app_source = APP.read_text()
      pending_source = PENDING_SOURCE.read_text()

      assert "initialShareUrlProcessedRef" in app_source
      assert "sourceKey" in app_source
      assert "clearIfCurrent" in pending_source
      assert "setAuthError('Sign in to save this shared source.')" not in app_source
      assert 'setAuthError("Sign in to save this shared source.")' not in app_source
      assert "stored:${source.sourceUrl}" not in app_source
  ```

- [ ] **Step 2: Run pytest and verify failure**

  ```bash
  python -m pytest tests/test_mobile_signed_out_screen.py
  ```

  Expected: FAIL because the current App still sets the expected sign-in prompt through `authError`, uses `stored:${source.sourceUrl}`, and lacks the launch URL guard.

- [ ] **Step 3: Add stable pending-source state shape**

  In `mobile/App.tsx`, remove mixed raw/stored dedupe naming:

  ```ts
  type PendingSharedSourceState = PendingSharedSource & {
    shouldAutoSubmit: boolean;
  };
  ```

  Add refs:

  ```ts
  const handledSharedSourceKeysRef = useRef<Set<string>>(new Set());
  const submittingSharedSourceKeysRef = useRef<Set<string>>(new Set());
  const pendingSharedSourceRef = useRef<PendingSharedSourceState | null>(null);
  const authStateRef = useRef({ isAuthLoading: true, isSignedIn: false });
  const initialShareUrlProcessedRef = useRef(false);
  ```

  Keep refs current:

  ```ts
  useEffect(() => {
    pendingSharedSourceRef.current = pendingSharedSource;
  }, [pendingSharedSource]);

  useEffect(() => {
    authStateRef.current = { isAuthLoading, isSignedIn };
  }, [isAuthLoading, isSignedIn]);
  ```

- [ ] **Step 4: Make restore unable to overwrite a fresh share**

  Change pending-store restore to set state only when nothing newer is already in memory:

  ```ts
  setPendingSharedSource((currentSource) => {
    if (currentSource) {
      return currentSource;
    }
    return {
      ...source,
      shouldAutoSubmit: false,
    };
  });
  ```

- [ ] **Step 5: Use sourceKey for incoming dedupe**

  In `handleIncomingShareLink`, derive and use `sourceKey` from the valid parse result:

  ```ts
  const sourceKey = result.sourceUrl;
  if (
    handledSharedSourceKeysRef.current.has(sourceKey) ||
    submittingSharedSourceKeysRef.current.has(sourceKey)
  ) {
    return;
  }
  submittingSharedSourceKeysRef.current.add(sourceKey);
  ```

  For signed-in users, set in-memory state:

  ```ts
  setPendingSharedSource({
    sourceUrl: result.sourceUrl,
    sourceKey,
    createdAtMs: Date.now(),
    shouldAutoSubmit: true,
  });
  ```

  For signed-out or auth-loading users, save canonical state:

  ```ts
  void pendingSharedSourceStore
    .save(result.sourceUrl)
    .then((source) => {
      submittingSharedSourceKeysRef.current.delete(sourceKey);
      setPendingSharedSource((currentSource) => {
        if (currentSource && currentSource.createdAtMs > source.createdAtMs) {
          return currentSource;
        }
        return {
          ...source,
          shouldAutoSubmit: authStateRef.current.isAuthLoading,
        };
      });
    })
    .catch((error) => {
      submittingSharedSourceKeysRef.current.delete(sourceKey);
      setPendingSharedSource((currentSource) => currentSource ?? {
        sourceUrl: result.sourceUrl,
        sourceKey,
        createdAtMs: Date.now(),
        shouldAutoSubmit: authStateRef.current.isAuthLoading,
      });
      if (!authStateRef.current.isAuthLoading) {
        setAuthError(errorMessage(error, 'Could not keep that shared source. Try sharing it again.'));
      }
    });
  ```

  Do not call `setAuthError('Sign in to save this shared source.')`; the signed-out screen already renders the expected pending-source prompt.

- [ ] **Step 6: Process initial URL once and keep event listener live**

  Split initial URL and event URL handling:

  ```ts
  useEffect(() => {
    if (initialShareUrlProcessedRef.current) {
      return;
    }
    initialShareUrlProcessedRef.current = true;

    let isMounted = true;
    void Linking.getInitialURL()
      .then((url) => {
        if (isMounted && url) {
          handleIncomingShareLink(url);
        }
      })
      .catch(() => undefined);

    return () => {
      isMounted = false;
    };
  }, [handleIncomingShareLink]);

  useEffect(() => {
    const subscription = Linking.addEventListener('url', (event) => {
      handleIncomingShareLink(event.url);
    });

    return () => {
      subscription.remove();
    };
  }, [handleIncomingShareLink]);
  ```

  Because `handleIncomingShareLink` reads auth through `authStateRef`, auth transitions do not require replaying the launch URL.

- [ ] **Step 7: Compare before clearing pending state**

  Update `clearPendingSharedSource` to accept an expected source key:

  ```ts
  const clearPendingSharedSource = useCallback(async (expectedSourceKey?: string) => {
    const currentSource = pendingSharedSourceRef.current;
    if (expectedSourceKey && currentSource?.sourceKey !== expectedSourceKey) {
      return;
    }

    if (currentSource) {
      submittingSharedSourceKeysRef.current.delete(currentSource.sourceKey);
    }
    try {
      if (expectedSourceKey) {
        await pendingSharedSourceStore.clearIfCurrent(expectedSourceKey);
      } else {
        await pendingSharedSourceStore.clear();
      }
    } catch {
      // Local cleanup should not block clearing the in-memory prompt.
    }
    setPendingSharedSource((latestSource) => {
      if (expectedSourceKey && latestSource?.sourceKey !== expectedSourceKey) {
        return latestSource;
      }
      return null;
    });
  }, []);
  ```

  Update discard:

  ```ts
  const discardPendingSharedSource = useCallback(async () => {
    await clearPendingSharedSource(pendingSharedSourceRef.current?.sourceKey);
    setAuthError(null);
    clearSharedCaptureError();
  }, [clearPendingSharedSource, clearSharedCaptureError]);
  ```

- [ ] **Step 8: Guard submit callbacks against stale pending sources**

  In `submitPendingSharedSource`, capture `sourceKey` and only mutate state for the same pending source:

  ```ts
  const source = pendingSharedSourceRef.current;
  if (!source || !isSignedIn) {
    return;
  }

  const didSubmit = await submitSharedUrl(source.sourceUrl);
  submittingSharedSourceKeysRef.current.delete(source.sourceKey);

  if (pendingSharedSourceRef.current?.sourceKey !== source.sourceKey) {
    return;
  }

  if (didSubmit) {
    handledSharedSourceKeysRef.current.add(source.sourceKey);
    await clearPendingSharedSource(source.sourceKey);
    clearSharedCaptureError();
    setSheet((currentSheet) => (currentSheet === 'paste' ? null : currentSheet));
    return;
  }
  ```

  On failed submit, keep the same guarded `setPendingSharedSource` pattern:

  ```ts
  setPendingSharedSource((currentSource) =>
    currentSource?.sourceKey === source.sourceKey
      ? { ...currentSource, shouldAutoSubmit: false }
      : currentSource,
  );
  ```

- [ ] **Step 9: Remove expected pending-state auth error**

  In the pending-submit effect, remove the signed-out `setAuthError` call:

  ```ts
  if (!isSignedIn) {
    if (pendingSharedSource.shouldAutoSubmit) {
      setPendingSharedSource((currentSource) =>
        currentSource?.sourceKey === pendingSharedSource.sourceKey
          ? { ...currentSource, shouldAutoSubmit: false }
          : currentSource,
      );
    }
    return;
  }
  ```

- [ ] **Step 10: Run focused checks**

  ```bash
  python -m pytest tests/test_mobile_signed_out_screen.py
  cd mobile && npm run test:pending-shared-source
  cd mobile && npm run test:share-url
  cd mobile && npm run typecheck
  ```

  Expected: all pass.

## Task 5: Document Production Mobile Auth Guard Behavior

**Files:**
- Modify: `mobile/README.md`

- [ ] **Step 1: Update production configuration docs**

  In the production config section, add:

  ```md
  Production mobile builds reject local or non-HTTPS Supabase URLs, Supabase secret/service-role
  keys, and `EXPO_PUBLIC_AUTH_REDIRECT_URL`. Use `EXPO_PUBLIC_AUTH_REDIRECT_URL` only for
  development sessions such as Expo Go or tunnel testing.
  ```

- [ ] **Step 2: Verify docs contain the new guard wording**

  ```bash
  rg -n "secret/service-role|EXPO_PUBLIC_AUTH_REDIRECT_URL" mobile/README.md
  ```

  Expected: matches the new production guard note and the existing development override section.

## Task 6: Full Mobile Validation

**Files:**
- No additional file changes.

- [ ] **Step 1: Run all mobile hardening scripts**

  ```bash
  cd mobile && npm run test:share-url
  cd mobile && npm run test:pending-shared-source
  cd mobile && npm run test:supabase-config
  cd mobile && npm run typecheck
  ```

  Expected: all commands pass.

- [ ] **Step 2: Run focused Python regression**

  ```bash
  python -m pytest tests/test_mobile_signed_out_screen.py
  ```

  Expected: all tests pass.

- [ ] **Step 3: Optional full backend test sweep**

  ```bash
  python -m pytest
  ```

  Expected: pass. This is optional for the mobile-only hardening change, but preferred before shipping because the repository is small.

- [ ] **Step 4: Manual iOS smoke test**

  With Supabase Auth configured and a reachable backend:

  ```bash
  cd mobile && npm run ios
  ```

  Manual checks:

  1. Sign out.
  2. Share `https://www.instagram.com/reel/SMOKE/?access_token=secret&utm_source=x` into Mentioned.
  3. Confirm the signed-out screen shows one pending-source prompt and does not show a duplicate error message.
  4. Close and reopen the app.
  5. Confirm the pending source is still shown as `https://www.instagram.com/reel/SMOKE/`.
  6. Sign in.
  7. Confirm the signed-in home shows one pending source prompt.
  8. Tap Save source.
  9. Confirm a processing capture appears and the prompt disappears.
  10. Repeat with Discard and confirm local pending state clears after app restart.

## Backend Idempotency Follow-Up

Do not implement backend idempotency in this mobile hardening pass. Create a separate plan if the team wants at-least-once share delivery to be idempotent server-side.

Recommended follow-up shape:

- Add optional `client_submission_id` to `CreateJobRequest`.
- Add nullable `client_submission_id` column to `jobs`.
- Add unique index on `(owner_id, client_submission_id)` where `client_submission_id is not null`.
- Reuse an existing job for the same owner/submission ID and do not increment quotas for reused jobs.
- Generate mobile submission ID from the canonical shared-source key only if the product accepts one active job per source share identity.
- Add Alembic migration under `migrations/versions/` and use Supabase CLI verification before hosted push, per repo policy.
- Add focused tests in `tests/jobs/test_router.py`, `tests/jobs/test_service.py`, and RLS migration source tests.

## Validation

```bash
cd mobile && npm run test:share-url
cd mobile && npm run test:pending-shared-source
cd mobile && npm run test:supabase-config
cd mobile && npm run typecheck
python -m pytest tests/test_mobile_signed_out_screen.py
```

Optional final sweep:

```bash
python -m pytest
```

## Acceptance Criteria

- [ ] Supported Instagram shared-source URLs are persisted without query params or hashes.
- [ ] Pending storage persists only canonical `sourceUrl`, `sourceKey`, and `createdAtMs`.
- [ ] Raw deep links, restored pending records, submit guards, and handled sets use the same `sourceKey`.
- [ ] `Linking.getInitialURL()` is read once per app lifetime and is not replayed by auth state changes.
- [ ] A restored stale pending source cannot overwrite a newer incoming share.
- [ ] A stale submit or discard callback cannot clear a newer pending source.
- [ ] Signed-out pending state shows through pending-source UI only, without duplicate `authError` copy.
- [ ] Production mobile config rejects unsafe Supabase key/redirect values.
- [ ] Runtime artifacts, secrets, `.env`, local databases, and generated outputs are not staged.
- [ ] Backend idempotency is explicitly tracked as separate schema/API work, not silently bundled into this mobile pass.
