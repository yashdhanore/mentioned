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

const sourceUrl = 'https://www.instagram.com/reel/PENDING/?token=secret&utm_source=x';
const canonicalUrl = 'https://www.instagram.com/reel/PENDING/';
const record = createPendingSharedSource(sourceUrl, 1_800_000_000_000);
const serialized = serializePendingSharedSource(record);

assert.deepEqual(record, {
  sourceUrl: canonicalUrl,
  sourceKey: canonicalUrl,
  createdAtMs: 1_800_000_000_000,
});
assert.deepEqual(JSON.parse(serialized), {
  sourceUrl: canonicalUrl,
  sourceKey: canonicalUrl,
  createdAtMs: 1_800_000_000_000,
});
assert.equal(serialized.includes('rawUrl'), false);
assert.equal(serialized.toLowerCase().includes('token'), false);
assert.equal(serialized.toLowerCase().includes('authorization'), false);
assert.deepEqual(parsePendingSharedSource(serialized), record);
assert.equal(parsePendingSharedSource(null), null);
assert.equal(parsePendingSharedSource('{bad json'), null);
assert.equal(
  parsePendingSharedSource(
    JSON.stringify({ sourceUrl: 'https://example.com/reel/PENDING/', createdAtMs: 1 }),
  ),
  null,
);
assert.equal(parsePendingSharedSource(JSON.stringify({ sourceUrl, createdAtMs: 'now' })), null);

async function main() {
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

  const first = await store.save('https://www.instagram.com/reel/FIRST/', 1);
  assert.equal(await store.clearIfCurrent('https://www.instagram.com/reel/OTHER/'), false);
  assert.deepEqual(await store.load(), first);
  assert.equal(await store.clearIfCurrent(first.sourceKey), true);
  assert.equal(await store.load(), null);

  const stale = await store.save('https://www.instagram.com/reel/STALE/', 2);
  const fresh = await store.save('https://www.instagram.com/reel/FRESH/', 3);
  assert.equal(await store.clearIfCurrent(stale.sourceKey), false);
  assert.deepEqual(await store.load(), fresh);

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

  console.log('pending shared source tests passed');
}

void main();
