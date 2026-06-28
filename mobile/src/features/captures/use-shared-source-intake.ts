import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Linking from 'expo-linking';
import { useCallback, useEffect, useRef, useState } from 'react';

import { errorMessage } from '@/api';
import {
  createPendingSharedSourceStore,
  type PendingSharedSource,
} from '@/features/captures/pending-shared-source';
import { parseMentionedShareDeepLink } from '@/utils/shared-source-url';

type PendingSharedSourceState = PendingSharedSource & {
  shouldAutoSubmit: boolean;
};

type UseSharedSourceIntakeOptions = {
  isAuthLoading: boolean;
  isSignedIn: boolean;
  submitSharedUrl: (sourceUrl: string) => Promise<boolean>;
  setSelectedCaptureId: (captureId: string | null) => void;
  setSharedCaptureError: (message: string) => void;
  clearSharedCaptureError: () => void;
  setAuthError: (message: string | null) => void;
  closePasteSheet: () => void;
};

type UseSharedSourceIntakeResult = {
  pendingSharedSourceUrl: string | null;
  shareLinkError: string | null;
  submitPendingSharedSource: () => Promise<void>;
  discardPendingSharedSource: () => Promise<void>;
};

const INVALID_SHARED_SOURCE_MESSAGE = 'Share an Instagram Reel or post link to save it.';
const pendingSharedSourceStore = createPendingSharedSourceStore(AsyncStorage);

export function useSharedSourceIntake({
  isAuthLoading,
  isSignedIn,
  submitSharedUrl,
  setSelectedCaptureId,
  setSharedCaptureError,
  clearSharedCaptureError,
  setAuthError,
  closePasteSheet,
}: UseSharedSourceIntakeOptions): UseSharedSourceIntakeResult {
  const [shareLinkError, setShareLinkError] = useState<string | null>(null);
  const [pendingSharedSource, setPendingSharedSource] =
    useState<PendingSharedSourceState | null>(null);
  const handledSharedSourceKeysRef = useRef<Set<string>>(new Set());
  const inFlightShareKeyRef = useRef<string | null>(null);
  const pendingSharedSourceRef = useRef<PendingSharedSourceState | null>(null);
  const authStateRef = useRef({ isAuthLoading: true, isSignedIn: false });
  const initialShareUrlProcessedRef = useRef(false);

  useEffect(() => {
    pendingSharedSourceRef.current = pendingSharedSource;
    if (pendingSharedSource?.sourceKey === inFlightShareKeyRef.current) {
      inFlightShareKeyRef.current = null;
    }
  }, [pendingSharedSource]);

  useEffect(() => {
    authStateRef.current = { isAuthLoading, isSignedIn };
  }, [isAuthLoading, isSignedIn]);

  useEffect(() => {
    let isMounted = true;

    void pendingSharedSourceStore
      .load()
      .then((source) => {
        if (!isMounted || !source) {
          return;
        }
        setPendingSharedSource((currentSource) => {
          if (currentSource) {
            return currentSource;
          }
          return { ...source, shouldAutoSubmit: false };
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
  }, [setAuthError]);

  const handleIncomingShareLink = useCallback(
    (url: string) => {
      const result = parseMentionedShareDeepLink(url);
      if (result.type === 'non-share-link') {
        return;
      }

      if (result.type === 'invalid-share-link') {
        setSelectedCaptureId(null);
        setShareLinkError(INVALID_SHARED_SOURCE_MESSAGE);
        setSharedCaptureError(INVALID_SHARED_SOURCE_MESSAGE);
        closePasteSheet();
        return;
      }

      const sourceKey = result.sourceUrl;
      if (
        handledSharedSourceKeysRef.current.has(sourceKey) ||
        pendingSharedSourceRef.current?.sourceKey === sourceKey ||
        inFlightShareKeyRef.current === sourceKey
      ) {
        return;
      }

      clearSharedCaptureError();
      setShareLinkError(null);
      inFlightShareKeyRef.current = sourceKey;

      if (!authStateRef.current.isAuthLoading && authStateRef.current.isSignedIn) {
        setPendingSharedSource({
          sourceUrl: result.sourceUrl,
          sourceKey,
          createdAtMs: Date.now(),
          shouldAutoSubmit: true,
        });
        return;
      }

      void pendingSharedSourceStore
        .save(result.sourceUrl)
        .then((source) => {
          setPendingSharedSource((currentSource) => {
            if (currentSource && currentSource.createdAtMs > source.createdAtMs) {
              return currentSource;
            }
            return { ...source, shouldAutoSubmit: authStateRef.current.isAuthLoading };
          });
        })
        .catch((error) => {
          if (inFlightShareKeyRef.current === sourceKey) {
            inFlightShareKeyRef.current = null;
          }
          setPendingSharedSource((currentSource) =>
            currentSource ?? {
              sourceUrl: result.sourceUrl,
              sourceKey,
              createdAtMs: Date.now(),
              shouldAutoSubmit: authStateRef.current.isAuthLoading,
            },
          );
          if (!authStateRef.current.isAuthLoading) {
            setAuthError(errorMessage(error, 'Could not keep that shared source. Try sharing it again.'));
          }
        });
    },
    [
      clearSharedCaptureError,
      closePasteSheet,
      setAuthError,
      setSelectedCaptureId,
      setSharedCaptureError,
    ],
  );

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

  const clearPendingSharedSource = useCallback(async (expectedSourceKey?: string) => {
    const currentSource = pendingSharedSourceRef.current;
    if (expectedSourceKey && currentSource?.sourceKey !== expectedSourceKey) {
      return;
    }

    if (currentSource && inFlightShareKeyRef.current === currentSource.sourceKey) {
      inFlightShareKeyRef.current = null;
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

  const discardPendingSharedSource = useCallback(async () => {
    await clearPendingSharedSource(pendingSharedSourceRef.current?.sourceKey);
    setShareLinkError(null);
    setAuthError(null);
    clearSharedCaptureError();
  }, [clearPendingSharedSource, clearSharedCaptureError, setAuthError]);

  const submitPendingSharedSource = useCallback(async () => {
    const source = pendingSharedSourceRef.current;
    if (!source || !isSignedIn) {
      return;
    }

    const didSubmit = await submitSharedUrl(source.sourceUrl);

    if (pendingSharedSourceRef.current?.sourceKey !== source.sourceKey) {
      return;
    }

    if (didSubmit) {
      handledSharedSourceKeysRef.current.add(source.sourceKey);
      await clearPendingSharedSource(source.sourceKey);
      setShareLinkError(null);
      clearSharedCaptureError();
      closePasteSheet();
      return;
    }

    setPendingSharedSource((currentSource) =>
      currentSource?.sourceKey === source.sourceKey
        ? { ...currentSource, shouldAutoSubmit: false }
        : currentSource,
    );
    setSelectedCaptureId(null);
    closePasteSheet();
  }, [
    clearPendingSharedSource,
    clearSharedCaptureError,
    closePasteSheet,
    isSignedIn,
    setSelectedCaptureId,
    submitSharedUrl,
  ]);

  useEffect(() => {
    if (!pendingSharedSource || isAuthLoading) {
      return;
    }

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

    if (pendingSharedSource.shouldAutoSubmit) {
      void submitPendingSharedSource();
    }
  }, [isAuthLoading, isSignedIn, pendingSharedSource, submitPendingSharedSource]);

  return {
    pendingSharedSourceUrl: pendingSharedSource?.sourceUrl ?? null,
    shareLinkError,
    submitPendingSharedSource,
    discardPendingSharedSource,
  };
}
