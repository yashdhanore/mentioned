# Preserve Shared Source Through Sign-In Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve a native-shared Instagram source while the user is signed out, guide them through sign-in, then let them save or discard the pending source without storing auth secrets.

**Architecture:** Add a focused pending shared-source store around AsyncStorage that persists only `{ sourceUrl, createdAtMs }`. Keep `mobile/App.tsx` as the coordinator for auth, deep links, and submission, but move storage encoding/decoding into a helper. Already-signed-in share links continue to submit immediately; signed-out shares are persisted, shown on the signed-out screen, then shown as a signed-in Save/Discard prompt after auth succeeds.

**Tech Stack:** Expo React Native, TypeScript, Supabase Auth, `@react-native-async-storage/async-storage`, existing `/v1/jobs` API client.

---

## Summary

Issue 15 is mobile-only. The app already parses `mentioned://share?url=...` links and can submit a shared URL through `submitSharedUrl(sourceUrl)`. The missing piece is durable pending-source state for the signed-out path and UI that makes the sign-in requirement explicit.

The implementation should:

- Persist only the normalized Instagram source URL and a timestamp.
- Avoid storing raw deep links, OAuth callback URLs, access tokens, refresh tokens, or provider data.
- Show signed-out copy explaining that sign-in is needed before saving the shared source.
- After sign-in, prompt the user to save or discard the pending source.
- Clear pending storage after successful submission or explicit discard.
- Preserve issue 14 behavior for already-signed-in native shares.

## Scope

- In: mobile pending-source storage, signed-out pending-source copy, signed-in Save/Discard prompt, submission/cancel handlers, typecheck/script validation.
- Out: backend API changes, database migrations, Supabase config changes, share-extension activation changes, Android share intents, extraction behavior.

## Issue

- GitHub Issue: #15
- URL: https://github.com/yashdhanore/mentioned/issues/15
- State: OPEN

## Patterns To Follow

| Area | Source | Pattern |
|------|--------|---------|
| Auth state | `mobile/App.tsx` | Restore Supabase session first, then render signed-out or signed-in surfaces based on `isSignedIn`. |
| Share parsing | `mobile/src/utils/shared-source-url.ts` | Trust `parseMentionedShareDeepLink` for normalized supported `/reel/` and `/p/` source URLs. |
| Shared submission | `mobile/src/features/captures/use-captures.ts` | Reuse `submitSharedUrl(sourceUrl)` so job creation, optimistic capture insertion, and selected capture behavior stay centralized. |
| Native persistence | `mobile/src/supabase.ts` | AsyncStorage is already used for native Supabase session persistence; use the same package for pending source storage. |
| Signed-out UI | `mobile/src/screens/signed-out-screen.tsx` | Keep the existing single Google sign-in path and render calm inline messages through `InlineMessage`. |
| Home UI | `mobile/src/screens/home-screen.tsx` | Render compact state surfaces above the capture grid, without exposing backend/provider details. |
| Validation | `mobile/package.json` | Use `npm run typecheck`; add a small `tsx` script only for pure pending-source storage behavior. |

## Files To Change

| File | Action | Purpose |
|------|--------|---------|
| `mobile/src/features/captures/pending-shared-source.ts` | CREATE | Encapsulate pending-source record shape, serialization, parsing, and injectable AsyncStorage-backed store helpers. |
| `mobile/scripts/test-pending-shared-source.ts` | CREATE | Verify pending-source storage keeps only non-secret source metadata and supports save/load/clear with fake storage. |
| `mobile/package.json` | UPDATE | Add `test:pending-shared-source` script. |
| `mobile/App.tsx` | UPDATE | Load persisted pending source, persist signed-out shares, prompt after sign-in, submit/discard pending source, and clear storage on success/cancel. |
| `mobile/src/screens/signed-out-screen.tsx` | UPDATE | Show pending-source sign-in explanation and Discard action. |
| `mobile/src/screens/home-screen.tsx` | UPDATE | Show a signed-in pending-source Save/Discard prompt after sign-in. |
| `mobile/src/styles.ts` | UPDATE | Add restrained prompt styles for pending-source surfaces. |
| `tests/test_mobile_signed_out_screen.py` | UPDATE | Extend source-level regression coverage for pending-source signed-out copy and unsupported Apple auth guard. |

## Tasks

### Task 1: Add pending shared-source storage helper

**Files:**
- Create: `mobile/src/features/captures/pending-shared-source.ts`
- Create: `mobile/scripts/test-pending-shared-source.ts`
- Modify: `mobile/package.json`

- [ ] **Step 1: Add the script command**

  Add this script in `mobile/package.json`:

  ```json
  "test:pending-shared-source": "tsx scripts/test-pending-shared-source.ts"
  ```

- [ ] **Step 2: Write the pending-source script test**

  Create `mobile/scripts/test-pending-shared-source.ts`:

  ```ts
  import assert from 'node:assert/strict';

  import {
    PENDING_SHARED_SOURCE_STORAGE_KEY,
    createPendingSharedSource,
    createPendingSharedSourceStore,
    parsePendingSharedSource,
    serializePendingSharedSource,
  } from '../src/features/captures/pending-shared-source';

  class MemoryStorage {
    values = new Map<string, string>();

    async getItem(key: string): Promise<string | null> {
      return this.values.get(key) ?? null;
    }

    async setItem(key: string, value: string): Promise<void> {
      this.values.set(key, value);
    }

    async removeItem(key: string): Promise<void> {
      this.values.delete(key);
    }
  }

  const sourceUrl = 'https://www.instagram.com/reel/PENDING/';
  const record = createPendingSharedSource(sourceUrl, 1_800_000_000_000);
  const serialized = serializePendingSharedSource(record);

  assert.deepEqual(JSON.parse(serialized), {
    sourceUrl,
    createdAtMs: 1_800_000_000_000,
  });
  assert.equal(serialized.includes('rawUrl'), false);
  assert.equal(serialized.toLowerCase().includes('token'), false);
  assert.equal(serialized.toLowerCase().includes('authorization'), false);
  assert.deepEqual(parsePendingSharedSource(serialized), record);
  assert.equal(parsePendingSharedSource(null), null);
  assert.equal(parsePendingSharedSource('{bad json'), null);
  assert.equal(parsePendingSharedSource(JSON.stringify({ sourceUrl: 'https://example.com/reel/PENDING/', createdAtMs: 1 })), null);
  assert.equal(parsePendingSharedSource(JSON.stringify({ sourceUrl, createdAtMs: 'now' })), null);

  const storage = new MemoryStorage();
  const store = createPendingSharedSourceStore(storage);
  assert.equal(await store.load(), null);

  const saved = await store.save(sourceUrl, 1_800_000_000_000);
  assert.deepEqual(saved, record);
  assert.deepEqual(await store.load(), record);
  assert.equal(storage.values.has(PENDING_SHARED_SOURCE_STORAGE_KEY), true);

  await store.clear();
  assert.equal(await store.load(), null);
  assert.equal(storage.values.has(PENDING_SHARED_SOURCE_STORAGE_KEY), false);

  console.log('pending shared source tests passed');
  ```

- [ ] **Step 3: Run the script test and verify it fails before implementation**

  ```bash
  cd mobile
  npm run test:pending-shared-source
  ```

  Expected: FAIL with a module resolution error for `pending-shared-source`.

- [ ] **Step 4: Implement the helper**

  Create `mobile/src/features/captures/pending-shared-source.ts`:

  ```ts
  import { isSupportedSharedSourceUrl } from '../../utils/shared-source-url';

  export const PENDING_SHARED_SOURCE_STORAGE_KEY = 'mentioned.pending-shared-source.v1';

  export type PendingSharedSource = {
    sourceUrl: string;
    createdAtMs: number;
  };

  type KeyValueStorage = {
    getItem: (key: string) => Promise<string | null>;
    setItem: (key: string, value: string) => Promise<void>;
    removeItem: (key: string) => Promise<void>;
  };

  export function createPendingSharedSource(
    sourceUrl: string,
    createdAtMs = Date.now(),
  ): PendingSharedSource {
    return { sourceUrl, createdAtMs };
  }

  export function serializePendingSharedSource(source: PendingSharedSource): string {
    return JSON.stringify({
      sourceUrl: source.sourceUrl,
      createdAtMs: source.createdAtMs,
    });
  }

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
      return {
        sourceUrl: parsed.sourceUrl,
        createdAtMs: parsed.createdAtMs,
      };
    } catch {
      return null;
    }
  }

  export function createPendingSharedSourceStore(storage: KeyValueStorage) {
    return {
      async load(): Promise<PendingSharedSource | null> {
        const storedValue = await storage.getItem(PENDING_SHARED_SOURCE_STORAGE_KEY);
        const source = parsePendingSharedSource(storedValue);
        if (!source && storedValue) {
          await storage.removeItem(PENDING_SHARED_SOURCE_STORAGE_KEY);
        }
        return source;
      },
      async save(sourceUrl: string, createdAtMs = Date.now()): Promise<PendingSharedSource> {
        const source = createPendingSharedSource(sourceUrl, createdAtMs);
        await storage.setItem(PENDING_SHARED_SOURCE_STORAGE_KEY, serializePendingSharedSource(source));
        return source;
      },
      async clear(): Promise<void> {
        await storage.removeItem(PENDING_SHARED_SOURCE_STORAGE_KEY);
      },
    };
  }
  ```

- [ ] **Step 5: Run the pending-source script test**

  ```bash
  cd mobile
  npm run test:pending-shared-source
  ```

  Expected: PASS with `pending shared source tests passed`.

### Task 2: Persist signed-out shared sources and load existing pending state

**Files:**
- Modify: `mobile/App.tsx`

- [ ] **Step 1: Import AsyncStorage and the pending-source helper**

  Add imports near the top of `mobile/App.tsx`:

  ```ts
  import AsyncStorage from '@react-native-async-storage/async-storage';
  import {
    createPendingSharedSourceStore,
    type PendingSharedSource,
  } from '@/features/captures/pending-shared-source';
  ```

  Add a module-level store:

  ```ts
  const pendingSharedSourceStore = createPendingSharedSourceStore(AsyncStorage);
  ```

- [ ] **Step 2: Replace the local pending type with UI state**

  Replace the current local `PendingSharedSource` type with:

  ```ts
  type PendingSharedSourceState = PendingSharedSource & {
    dedupeKey: string;
    shouldAutoSubmit: boolean;
  };
  ```

  Update state:

  ```ts
  const [pendingSharedSource, setPendingSharedSource] = useState<PendingSharedSourceState | null>(null);
  ```

- [ ] **Step 3: Add storage load effect**

  Add an effect after the `useCaptures` block:

  ```ts
  useEffect(() => {
    let isMounted = true;

    void pendingSharedSourceStore
      .load()
      .then((source) => {
        if (!isMounted || !source) {
          return;
        }
        setPendingSharedSource({
          ...source,
          dedupeKey: `stored:${source.sourceUrl}`,
          shouldAutoSubmit: false,
        });
      })
      .catch(() => {
        if (isMounted) {
          setAuthError('Could not restore the shared source.');
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);
  ```

- [ ] **Step 4: Split incoming share handling by auth state**

  In `handleIncomingShareLink`, keep invalid link handling, then handle valid links this way:

  ```ts
  clearSharedCaptureError();
  submittingShareDeepLinksRef.current.add(url);

  if (!isAuthLoading && isSignedIn) {
    setPendingSharedSource({
      sourceUrl: result.sourceUrl,
      createdAtMs: Date.now(),
      dedupeKey: url,
      shouldAutoSubmit: true,
    });
    return;
  }

  void pendingSharedSourceStore
    .save(result.sourceUrl)
    .then((source) => {
      submittingShareDeepLinksRef.current.delete(url);
      setPendingSharedSource({
        ...source,
        dedupeKey: `stored:${source.sourceUrl}`,
        shouldAutoSubmit: false,
      });
      setAuthError('Sign in to save this shared source.');
    })
    .catch((error) => {
      submittingShareDeepLinksRef.current.delete(url);
      setPendingSharedSource({
        sourceUrl: result.sourceUrl,
        createdAtMs: Date.now(),
        dedupeKey: url,
        shouldAutoSubmit: false,
      });
      setAuthError(errorMessage(error, 'Could not keep that shared source. Try sharing it again.'));
    });
  ```

  Update the callback dependencies to include `isAuthLoading` and `isSignedIn`.

- [ ] **Step 5: Run typecheck**

  ```bash
  cd mobile
  npm run typecheck
  ```

  Expected: PASS.

### Task 3: Add pending source save/discard handlers

**Files:**
- Modify: `mobile/App.tsx`

- [ ] **Step 1: Include shared submission loading state**

  Destructure `isSubmittingSharedUrl` from `useCaptures(isSignedIn)`:

  ```ts
  isSubmittingSharedUrl,
  ```

- [ ] **Step 2: Add a helper to clear pending state**

  Add this callback before `handleSignIn`:

  ```ts
  const clearPendingSharedSource = useCallback(async () => {
    const currentSource = pendingSharedSource;
    if (currentSource) {
      submittingShareDeepLinksRef.current.delete(currentSource.dedupeKey);
    }
    try {
      await pendingSharedSourceStore.clear();
    } catch {
      // Local cleanup should not block clearing the in-memory prompt.
    }
    setPendingSharedSource(null);
  }, [pendingSharedSource]);
  ```

- [ ] **Step 3: Add explicit discard callback**

  Add this callback after `clearPendingSharedSource`:

  ```ts
  const discardPendingSharedSource = useCallback(async () => {
    await clearPendingSharedSource();
    setAuthError(null);
    clearSharedCaptureError();
  }, [clearPendingSharedSource, clearSharedCaptureError]);
  ```

- [ ] **Step 4: Add submit callback**

  Add this callback after `discardPendingSharedSource`:

  ```ts
  const submitPendingSharedSource = useCallback(async () => {
    const source = pendingSharedSource;
    if (!source || !isSignedIn) {
      return;
    }

    const didSubmit = await submitSharedUrl(source.sourceUrl);
    submittingShareDeepLinksRef.current.delete(source.dedupeKey);

    if (didSubmit) {
      handledShareDeepLinksRef.current.add(source.dedupeKey);
      await clearPendingSharedSource();
      clearSharedCaptureError();
      setSheet((currentSheet) => (currentSheet === 'paste' ? null : currentSheet));
      return;
    }

    setPendingSharedSource((currentSource) =>
      currentSource?.dedupeKey === source.dedupeKey
        ? { ...currentSource, shouldAutoSubmit: false }
        : currentSource,
    );
    setSelectedCaptureId(null);
    setSheet((currentSheet) => (currentSheet === 'paste' ? null : currentSheet));
  }, [
    clearPendingSharedSource,
    clearSharedCaptureError,
    isSignedIn,
    pendingSharedSource,
    setSelectedCaptureId,
    submitSharedUrl,
  ]);
  ```

- [ ] **Step 5: Narrow auto-submit effect to already-signed-in shares**

  Replace the existing pending-share submission effect with:

  ```ts
  useEffect(() => {
    if (!pendingSharedSource || isAuthLoading) {
      return;
    }

    if (!isSignedIn) {
      setAuthError('Sign in to save this shared source.');
      return;
    }

    if (pendingSharedSource.shouldAutoSubmit) {
      void submitPendingSharedSource();
    }
  }, [isAuthLoading, isSignedIn, pendingSharedSource, submitPendingSharedSource]);
  ```

  This keeps direct submission for shares received while signed in and turns stored signed-out shares into a prompt after sign-in.

- [ ] **Step 6: Run typecheck**

  ```bash
  cd mobile
  npm run typecheck
  ```

  Expected: PASS.

### Task 4: Update signed-out and signed-in pending-source UI

**Files:**
- Modify: `mobile/src/screens/signed-out-screen.tsx`
- Modify: `mobile/src/screens/home-screen.tsx`
- Modify: `mobile/src/styles.ts`
- Modify: `mobile/App.tsx`

- [ ] **Step 1: Add pending props to `SignedOutScreen`**

  Update `SignedOutScreen` props:

  ```ts
  pendingSharedSourceUrl,
  onDiscardPendingSharedSource,
  ```

  with types:

  ```ts
  pendingSharedSourceUrl: string | null;
  onDiscardPendingSharedSource: () => void;
  ```

  Render the warning before `error`:

  ```tsx
  {pendingSharedSourceUrl ? (
    <InlineMessage
      tone="warning"
      message="Sign in to save this shared source."
      actionLabel="Discard"
      onAction={onDiscardPendingSharedSource}
    />
  ) : null}
  ```

- [ ] **Step 2: Add pending props to `HomeScreen`**

  Update `HomeScreen` props:

  ```ts
  pendingSharedSourceUrl,
  isSubmittingPendingSharedSource,
  onSavePendingSharedSource,
  onDiscardPendingSharedSource,
  ```

  with types:

  ```ts
  pendingSharedSourceUrl: string | null;
  isSubmittingPendingSharedSource: boolean;
  onSavePendingSharedSource: () => void;
  onDiscardPendingSharedSource: () => void;
  ```

  Render the prompt after the home header and before errors:

  ```tsx
  {pendingSharedSourceUrl ? (
    <View style={styles.pendingSourcePrompt}>
      <View style={styles.pendingSourceCopy}>
        <Text style={styles.pendingSourceTitle}>Shared source ready</Text>
        <Text ellipsizeMode="middle" numberOfLines={1} style={styles.pendingSourceUrl}>
          {pendingSharedSourceUrl}
        </Text>
      </View>
      <View style={styles.pendingSourceActions}>
        <PrimaryButton
          label={isSubmittingPendingSharedSource ? 'Saving...' : 'Save source'}
          onPress={onSavePendingSharedSource}
          compact
          disabled={isSubmittingPendingSharedSource}
        />
        <SecondaryButton
          label="Discard"
          onPress={onDiscardPendingSharedSource}
          compact
          disabled={isSubmittingPendingSharedSource}
        />
      </View>
    </View>
  ) : null}
  ```

  Add `SecondaryButton` to the existing UI import.

- [ ] **Step 3: Add styles**

  Add these styles in `mobile/src/styles.ts` near the state/inline-message styles:

  ```ts
  pendingSourcePrompt: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.md,
    borderWidth: 1,
    gap: spacing.md,
    padding: spacing.md,
  },
  pendingSourceCopy: {
    gap: spacing.xs,
  },
  pendingSourceTitle: {
    ...typography.labelLg,
    color: colors.onSurface,
  },
  pendingSourceUrl: {
    ...typography.bodySm,
    color: colors.onMuted,
  },
  pendingSourceActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  ```

- [ ] **Step 4: Pass props from `App.tsx`**

  For `SignedOutScreen`:

  ```tsx
  <SignedOutScreen
    error={authError}
    pendingSharedSourceUrl={pendingSharedSource?.sourceUrl ?? null}
    isGoogleLoading={authProviderInFlight === 'google'}
    isDisabled={authProviderInFlight !== null}
    onContinueGoogle={() => void handleSignIn('google')}
    onDiscardPendingSharedSource={() => void discardPendingSharedSource()}
    privacyPolicyUrl={PRIVACY_POLICY_URL}
  />
  ```

  For `HomeScreen`:

  ```tsx
  <HomeScreen
    captures={captures}
    error={sharedCaptureError ?? loadError}
    errorActionLabel={sharedCaptureError ? undefined : 'Try again'}
    onErrorAction={sharedCaptureError ? undefined : () => void refreshCaptures()}
    pendingSharedSourceUrl={pendingSharedSource?.sourceUrl ?? null}
    isSubmittingPendingSharedSource={isSubmittingSharedUrl}
    onSavePendingSharedSource={() => void submitPendingSharedSource()}
    onDiscardPendingSharedSource={() => void discardPendingSharedSource()}
    isLoading={isLoadingCaptures}
    tileWidth={tileWidth}
    onOpenPaste={openPasteSheet}
    onOpenProfile={() => setSheet('profile')}
    onOpenCapture={openCapture}
  />
  ```

- [ ] **Step 5: Extend the Python signed-out regression test**

  Update `tests/test_mobile_signed_out_screen.py`:

  ```py
  PENDING_SOURCE = REPO_ROOT / "mobile" / "src" / "features" / "captures" / "pending-shared-source.ts"


  def test_signed_out_screen_explains_pending_shared_source() -> None:
      screen_source = SIGNED_OUT_SCREEN.read_text()
      app_source = APP.read_text()
      pending_source = PENDING_SOURCE.read_text()

      assert "Sign in to save this shared source." in screen_source
      assert "pendingSharedSourceUrl" in screen_source
      assert "onDiscardPendingSharedSource" in screen_source
      assert "pendingSharedSourceStore.clear" in app_source
      assert "sourceUrl" in pending_source
      assert "createdAtMs" in pending_source
      assert "access_token" not in pending_source
      assert "refresh_token" not in pending_source
  ```

- [ ] **Step 6: Run focused checks**

  ```bash
  python -m pytest tests/test_mobile_signed_out_screen.py
  cd mobile
  npm run typecheck
  ```

  Expected: both PASS.

### Task 5: Verify full behavior and artifact cleanliness

**Files:**
- No production edits unless validation exposes a bug.

- [ ] **Step 1: Run mobile script tests**

  ```bash
  cd mobile
  npm run test:share-url
  npm run test:pending-shared-source
  npm run typecheck
  ```

  Expected: all PASS.

- [ ] **Step 2: Run focused Python regression**

  ```bash
  python -m pytest tests/test_mobile_signed_out_screen.py
  ```

  Expected: PASS.

- [ ] **Step 3: Manual signed-out native share smoke test**

  With Supabase auth configured and the backend reachable:

  1. Sign out of the mobile app.
  2. Share a supported Instagram Reel/post URL to Mentioned from iOS.
  3. Confirm the signed-out screen shows "Sign in to save this shared source."
  4. Close and reopen the app before signing in.
  5. Confirm the same pending-source message remains.
  6. Sign in with Google.
  7. Confirm the signed-in home shows the pending shared source with Save source and Discard.
  8. Tap Save source.
  9. Confirm a processing capture is inserted/selected and pending-source prompt disappears.
  10. Sign out, repeat a share, tap Discard, and confirm the pending-source message is gone after reopening.

- [ ] **Step 4: Check git state**

  ```bash
  git status --short
  ```

  Expected: only intentional source/test/package files are modified; no `.expo`, `dist`, `node_modules`, local DBs, or generated artifacts are staged.

## Validation

```bash
cd mobile
npm run test:share-url
npm run test:pending-shared-source
npm run typecheck
cd ..
python -m pytest tests/test_mobile_signed_out_screen.py
```

Manual validation:

```text
Sign out, share a supported source to Mentioned, close/reopen the app, sign in, save the pending source, and verify it creates/selects a processing capture. Repeat and discard to verify cancellation clears local pending storage.
```

## Acceptance Criteria

- [ ] When a signed-out user shares a supported source to Mentioned, the app preserves `{ sourceUrl, createdAtMs }` locally.
- [ ] The signed-out screen explains that sign-in is needed before saving the shared source.
- [ ] After successful sign-in, the app prompts the user to save the pending source.
- [ ] Saving the pending source calls the existing `submitSharedUrl(sourceUrl)` path.
- [ ] The pending source is cleared after successful submission.
- [ ] The pending source is cleared after explicit Discard from signed-out or signed-in UI.
- [ ] Pending source storage does not include raw deep links, auth tokens, callback URLs, or user credentials.
- [ ] Already-signed-in native share links continue to submit directly.
- [ ] Paste-link capture continues to work.
- [ ] `npm run test:share-url`, `npm run test:pending-shared-source`, `npm run typecheck`, and focused Python regression pass.
- [ ] Generated/runtime artifacts are not staged.

## Main Risks

- The current `mobile/App.tsx` has uncommitted issue 14 changes; implement against that state and do not revert the duplicate-guard work.
- AsyncStorage persistence must not store raw deep links because raw URLs can contain arbitrary query params.
- Prompt-after-sign-in changes the stored signed-out path from automatic submission to explicit Save/Discard; this is allowed by issue 15 and gives a clear cancellation path.
- Without a React Native component test runner, UI validation is split between TypeScript checks, source-level regression tests, and manual native smoke testing.
