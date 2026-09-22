import assert from 'node:assert/strict';

import { decideIncomingShareLink } from '../src/features/captures/shared-source-intake-logic';

const baseContext = {
  handledSharedSourceKeys: new Set<string>(),
  pendingSourceKey: null,
  inFlightShareKey: null,
  isAuthLoading: false,
  isSignedIn: true,
};

const sourceUrl = 'https://www.instagram.com/reel/ABC123/';

assert.deepEqual(decideIncomingShareLink({ type: 'non-share-link' }, baseContext), {
  type: 'non-share-link',
});

assert.deepEqual(decideIncomingShareLink({ type: 'invalid-share-link' }, baseContext), {
  type: 'invalid-share-link',
});

// Signed in and not loading: accept immediately, no persistence needed.
assert.deepEqual(decideIncomingShareLink({ type: 'valid', sourceUrl }, baseContext), {
  type: 'accept',
  sourceUrl,
  sourceKey: sourceUrl,
  immediate: true,
});

// Still resolving auth: accept but defer, so the caller persists it.
assert.deepEqual(
  decideIncomingShareLink({ type: 'valid', sourceUrl }, { ...baseContext, isAuthLoading: true }),
  { type: 'accept', sourceUrl, sourceKey: sourceUrl, immediate: false },
);

// Signed out: accept but defer.
assert.deepEqual(
  decideIncomingShareLink({ type: 'valid', sourceUrl }, { ...baseContext, isSignedIn: false }),
  { type: 'accept', sourceUrl, sourceKey: sourceUrl, immediate: false },
);

// Already handled this source: duplicate, no-op.
assert.deepEqual(
  decideIncomingShareLink(
    { type: 'valid', sourceUrl },
    { ...baseContext, handledSharedSourceKeys: new Set([sourceUrl]) },
  ),
  { type: 'duplicate' },
);

// Already the pending source: duplicate.
assert.deepEqual(
  decideIncomingShareLink(
    { type: 'valid', sourceUrl },
    { ...baseContext, pendingSourceKey: sourceUrl },
  ),
  { type: 'duplicate' },
);

// Already in flight: duplicate.
assert.deepEqual(
  decideIncomingShareLink(
    { type: 'valid', sourceUrl },
    { ...baseContext, inFlightShareKey: sourceUrl },
  ),
  { type: 'duplicate' },
);

// A different source key is unaffected by unrelated handled/pending/in-flight keys.
const otherUrl = 'https://www.instagram.com/reel/OTHER/';
assert.deepEqual(
  decideIncomingShareLink(
    { type: 'valid', sourceUrl },
    {
      ...baseContext,
      handledSharedSourceKeys: new Set([otherUrl]),
      pendingSourceKey: otherUrl,
      inFlightShareKey: otherUrl,
    },
  ),
  { type: 'accept', sourceUrl, sourceKey: sourceUrl, immediate: true },
);

console.log('shared source intake decision tests passed');
