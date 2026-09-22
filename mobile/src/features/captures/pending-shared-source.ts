import {
  canonicalSharedSourceKey,
  isSupportedSharedSourceUrl,
} from '../../utils/shared-source-url';

export const PENDING_SHARED_SOURCE_STORAGE_KEY = 'mentioned.pending-shared-source.v1';

export type PendingSharedSource = {
  sourceUrl: string;
  sourceKey: string;
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

export function serializePendingSharedSource(source: PendingSharedSource): string {
  return JSON.stringify({
    sourceUrl: source.sourceUrl,
    sourceKey: source.sourceKey,
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
    return createPendingSharedSource(parsed.sourceUrl, parsed.createdAtMs);
  } catch {
    return null;
  }
}

export function createPendingSharedSourceStore(storage: KeyValueStorage) {
  const load = async (): Promise<PendingSharedSource | null> => {
    const storedValue = await storage.getItem(PENDING_SHARED_SOURCE_STORAGE_KEY);
    const source = parsePendingSharedSource(storedValue);
    if (!source && storedValue) {
      await storage.removeItem(PENDING_SHARED_SOURCE_STORAGE_KEY);
    }
    return source;
  };

  const save = async (
    sourceUrl: string,
    createdAtMs = Date.now(),
  ): Promise<PendingSharedSource> => {
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
