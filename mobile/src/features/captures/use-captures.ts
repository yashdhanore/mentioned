import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Linking } from 'react-native';

import {
  createSavedSource,
  deleteSavedSource,
  errorMessage,
  getSavedSource,
  listSavedSources,
} from '@/api';
import { captureFromSavedSource, type Capture } from '@/captures';
import { isAllowedInstagramUrl } from '@/utils/source-url';

type SubmitSourceOptions = {
  setSubmitting: (isSubmitting: boolean) => void;
  setError: (message: string | null) => void;
  fallbackError: string;
  onSuccess?: () => void;
};

type CaptureActionResult = { ok: true } | { ok: false; message: string };

const PROCESSING_CAPTURE_POLL_INTERVAL_MS = 4_000;

type UseCapturesResult = {
  captures: Capture[];
  selectedCapture: Capture | null;
  pasteUrl: string;
  isLoadingCaptures: boolean;
  isSubmittingUrl: boolean;
  isSubmittingSharedUrl: boolean;
  retryingCaptureId: string | null;
  deletingCaptureId: string | null;
  loadError: string | null;
  pasteError: string | null;
  sharedCaptureError: string | null;
  actionError: string | null;
  setSelectedCaptureId: (captureId: string | null) => void;
  setPasteUrl: (url: string) => void;
  clearPasteError: () => void;
  setSharedCaptureError: (message: string) => void;
  clearSharedCaptureError: () => void;
  refreshCaptures: (options?: { silent?: boolean }) => Promise<void>;
  openCapture: (capture: Capture) => void;
  openCaptureBySavedSourceId: (savedSourceId: string) => Promise<void>;
  submitPasteUrl: () => Promise<boolean>;
  submitSharedUrl: (sourceUrl: string) => Promise<boolean>;
  retryCapture: (capture: Capture) => Promise<void>;
  deleteCapture: (capture: Capture) => Promise<CaptureActionResult>;
  openSource: (capture: Capture) => Promise<void>;
};

export function useCaptures(isSignedIn: boolean): UseCapturesResult {
  const [captures, setCaptures] = useState<Capture[]>([]);
  const [selectedCaptureId, setSelectedCaptureId] = useState<string | null>(null);
  const [pasteUrl, setPasteUrlState] = useState('');
  const [isLoadingCaptures, setIsLoadingCaptures] = useState(false);
  const [isSubmittingUrl, setIsSubmittingUrl] = useState(false);
  const [isSubmittingSharedUrl, setIsSubmittingSharedUrl] = useState(false);
  const [retryingCaptureId, setRetryingCaptureId] = useState<string | null>(null);
  const [deletingCaptureId, setDeletingCaptureId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pasteError, setPasteError] = useState<string | null>(null);
  const [sharedCaptureError, setSharedCaptureErrorState] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const isSilentRefreshInFlightRef = useRef(false);

  const selectedCapture = useMemo(() => {
    return captures.find((capture) => capture.id === selectedCaptureId) ?? null;
  }, [captures, selectedCaptureId]);
  const hasProcessingCaptures = useMemo(() => {
    return captures.some((capture) => capture.status === 'processing');
  }, [captures]);

  const refreshCaptureById = useCallback(async (savedSourceId: string, options: { select?: boolean } = {}) => {
    const savedSource = await getSavedSource(savedSourceId);
    const updated = captureFromSavedSource(savedSource);
    setCaptures((current) => {
      const existing = current.find((item) => item.id === savedSourceId);
      if (!existing) {
        return [updated, ...current];
      }
      return current.map((item) => (item.id === savedSourceId ? updated : item));
    });
    if (options.select) {
      setSelectedCaptureId(savedSourceId);
    }
  }, []);

  const refreshCaptures = useCallback(
    async ({ silent = false }: { silent?: boolean } = {}) => {
      if (!isSignedIn) {
        return;
      }

      if (silent) {
        if (isSilentRefreshInFlightRef.current) {
          return;
        }
        isSilentRefreshInFlightRef.current = true;
      }

      if (!silent) {
        setIsLoadingCaptures(true);
      }
      setLoadError(null);

      try {
        const savedSources = await listSavedSources();
        setCaptures(savedSources.map((savedSource) => captureFromSavedSource(savedSource)));
      } catch (error) {
        setLoadError(errorMessage(error, 'Could not load saved items.'));
      } finally {
        if (silent) {
          isSilentRefreshInFlightRef.current = false;
        } else {
          setIsLoadingCaptures(false);
        }
      }
    },
    [isSignedIn],
  );

  useEffect(() => {
    if (!isSignedIn) {
      isSilentRefreshInFlightRef.current = false;
      setCaptures([]);
      setSelectedCaptureId(null);
      return;
    }

    void refreshCaptures();
  }, [isSignedIn, refreshCaptures]);

  useEffect(() => {
    if (!isSignedIn || !hasProcessingCaptures) {
      return undefined;
    }

    const interval = setInterval(() => {
      void refreshCaptures({ silent: true }).catch(() => undefined);
    }, PROCESSING_CAPTURE_POLL_INTERVAL_MS);

    return () => {
      clearInterval(interval);
    };
  }, [hasProcessingCaptures, isSignedIn, refreshCaptures]);

  const openCapture = useCallback(
    (capture: Capture) => {
      setActionError(null);
      setSelectedCaptureId(capture.id);
      void refreshCaptureById(capture.id).catch(() => undefined);
    },
    [refreshCaptureById],
  );

  const openCaptureBySavedSourceId = useCallback(
    async (savedSourceId: string) => {
      setActionError(null);
      await refreshCaptureById(savedSourceId, { select: true });
    },
    [refreshCaptureById],
  );

  const setPasteUrl = useCallback((value: string) => {
    setPasteError(null);
    setPasteUrlState(value);
  }, []);

  const clearPasteError = useCallback(() => {
    setPasteError(null);
  }, []);

  const setSharedCaptureError = useCallback((message: string) => {
    setSharedCaptureErrorState(message);
  }, []);

  const clearSharedCaptureError = useCallback(() => {
    setSharedCaptureErrorState(null);
  }, []);

  const submitSourceUrl = useCallback(
    async (sourceUrl: string, options: SubmitSourceOptions) => {
      options.setError(null);
      options.setSubmitting(true);

      try {
        const created = await createSavedSource(sourceUrl);
        const capture = captureFromSavedSource(created);
        setCaptures((current) => [capture, ...current.filter((item) => item.id !== capture.id)]);
        setSelectedCaptureId(capture.id);
        options.onSuccess?.();
        void refreshCaptureById(created.id).catch(() => undefined);
        return true;
      } catch (error) {
        options.setError(errorMessage(error, options.fallbackError));
        return false;
      } finally {
        options.setSubmitting(false);
      }
    },
    [refreshCaptureById],
  );

  const submitPasteUrl = useCallback(async () => {
    const url = pasteUrl.trim();
    if (!url) {
      setPasteError('Paste an Instagram Reel or post URL.');
      return false;
    }

    return submitSourceUrl(url, {
      setSubmitting: setIsSubmittingUrl,
      setError: setPasteError,
      fallbackError: 'Could not submit that Reel.',
      onSuccess: () => setPasteUrlState(''),
    });
  }, [pasteUrl, submitSourceUrl]);

  const submitSharedUrl = useCallback(
    async (sourceUrl: string) => {
      const url = sourceUrl.trim();
      if (!url) {
        setSharedCaptureErrorState('Share an Instagram Reel or post link to save it.');
        return false;
      }

      return submitSourceUrl(url, {
        setSubmitting: setIsSubmittingSharedUrl,
        setError: setSharedCaptureErrorState,
        fallbackError: 'Could not save that shared source.',
      });
    },
    [submitSourceUrl],
  );

  const retryCapture = useCallback(
    async (capture: Capture) => {
      setActionError(null);
      setRetryingCaptureId(capture.id);

      try {
        const created = await createSavedSource(capture.sourceUrl);
        const updatedCapture = captureFromSavedSource(created);
        setCaptures((current) => [
          updatedCapture,
          ...current.filter((item) => item.id !== capture.id),
        ]);
        setSelectedCaptureId(updatedCapture.id);
        void refreshCaptureById(created.id).catch(() => undefined);
      } catch (error) {
        setActionError(errorMessage(error, 'Could not retry this Reel.'));
      } finally {
        setRetryingCaptureId(null);
      }
    },
    [refreshCaptureById],
  );

  const deleteCapture = useCallback(async (capture: Capture): Promise<CaptureActionResult> => {
    setActionError(null);
    setDeletingCaptureId(capture.id);

    try {
      await deleteSavedSource(capture.id);
      setCaptures((current) => current.filter((item) => item.id !== capture.id));
      setSelectedCaptureId((currentId) => (currentId === capture.id ? null : currentId));
      return { ok: true };
    } catch (error) {
      const message = errorMessage(error, 'Could not delete this post.');
      setActionError(message);
      return { ok: false, message };
    } finally {
      setDeletingCaptureId(null);
    }
  }, []);

  const openSource = useCallback(async (capture: Capture) => {
    setActionError(null);
    if (!isAllowedInstagramUrl(capture.sourceUrl)) {
      setActionError('This Instagram URL cannot be opened from the app.');
      return;
    }
    try {
      await Linking.openURL(capture.sourceUrl);
    } catch (error) {
      setActionError(errorMessage(error, 'Could not open Instagram.'));
    }
  }, []);

  return {
    captures,
    selectedCapture,
    pasteUrl,
    isLoadingCaptures,
    isSubmittingUrl,
    isSubmittingSharedUrl,
    retryingCaptureId,
    deletingCaptureId,
    loadError,
    pasteError,
    sharedCaptureError,
    actionError,
    setSelectedCaptureId,
    setPasteUrl,
    clearPasteError,
    setSharedCaptureError,
    clearSharedCaptureError,
    refreshCaptures,
    openCapture,
    openCaptureBySavedSourceId,
    submitPasteUrl,
    submitSharedUrl,
    retryCapture,
    deleteCapture,
    openSource,
  };
}
