import { useCallback, useEffect, useMemo, useState } from 'react';
import { Linking } from 'react-native';

import { createJob, deleteMention, errorMessage, getJob, listAllJobs } from '@/api';
import {
  buildCaptures,
  captureFromJobCreated,
  captureFromJobDetail,
  type Capture,
} from '@/captures';
import { isSupabaseConfigured, supabase } from '@/supabase';
import { isAllowedInstagramUrl } from '@/utils/source-url';

type JobEventRecord = {
  job_id?: string;
};

type SubmitSourceOptions = {
  setSubmitting: (isSubmitting: boolean) => void;
  setError: (message: string | null) => void;
  fallbackError: string;
  onSuccess?: () => void;
};

type RemoveBookResult = { ok: true } | { ok: false; message: string };

type UseCapturesResult = {
  captures: Capture[];
  selectedCapture: Capture | null;
  pasteUrl: string;
  isLoadingCaptures: boolean;
  isSubmittingUrl: boolean;
  isSubmittingSharedUrl: boolean;
  retryingCaptureId: string | null;
  removingBookId: string | null;
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
  openCaptureByJobId: (jobId: string) => Promise<void>;
  submitPasteUrl: () => Promise<boolean>;
  submitSharedUrl: (sourceUrl: string) => Promise<boolean>;
  retryCapture: (capture: Capture) => Promise<void>;
  removeBookMention: (capture: Capture, bookId: string) => Promise<RemoveBookResult>;
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
  const [removingBookId, setRemovingBookId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pasteError, setPasteError] = useState<string | null>(null);
  const [sharedCaptureError, setSharedCaptureErrorState] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const selectedCapture = useMemo(() => {
    return captures.find((capture) => capture.id === selectedCaptureId) ?? null;
  }, [captures, selectedCaptureId]);

  const refreshCaptureById = useCallback(async (jobId: string, options: { select?: boolean } = {}) => {
    const job = await getJob(jobId);
    const updated = captureFromJobDetail(job);
    setCaptures((current) => {
      const existing = current.find((item) => item.id === jobId);
      if (!existing) {
        return [updated, ...current];
      }
      return current.map((item) => (item.id === jobId ? updated : item));
    });
    if (options.select) {
      setSelectedCaptureId(jobId);
    }
  }, []);

  const refreshCaptures = useCallback(
    async ({ silent = false }: { silent?: boolean } = {}) => {
      if (!isSignedIn) {
        return;
      }

      if (!silent) {
        setIsLoadingCaptures(true);
      }
      setLoadError(null);

      try {
        const jobs = await listAllJobs();
        const jobDetails = await Promise.all(jobs.map((job) => getJob(job.job_id)));
        setCaptures(buildCaptures(jobDetails));
      } catch (error) {
        setLoadError(errorMessage(error, 'Could not load saved items.'));
      } finally {
        if (!silent) {
          setIsLoadingCaptures(false);
        }
      }
    },
    [isSignedIn],
  );

  useEffect(() => {
    if (!isSignedIn) {
      setCaptures([]);
      setSelectedCaptureId(null);
      return;
    }

    void refreshCaptures();
  }, [isSignedIn, refreshCaptures]);

  useEffect(() => {
    if (!isSignedIn || !isSupabaseConfigured) {
      return undefined;
    }

    let isActive = true;
    let channel: ReturnType<typeof supabase.channel> | null = null;

    void supabase.auth
      .getSession()
      .then(({ data }) => {
        if (!isActive) {
          return;
        }

        const userId = data.session?.user.id;
        if (!userId) {
          return;
        }

        channel = supabase
          .channel(`mentioned-job-events:${userId}`)
          .on(
            'postgres_changes',
            {
              event: 'INSERT',
              schema: 'public',
              table: 'job_events',
              filter: `owner_id=eq.${userId}`,
            },
            (payload) => {
              const event = payload.new as JobEventRecord;
              if (event.job_id) {
                void refreshCaptureById(event.job_id).catch(() => undefined);
              }
            },
          )
          .subscribe();
      })
      .catch(() => undefined);

    return () => {
      isActive = false;
      if (channel) {
        void supabase.removeChannel(channel);
      }
    };
  }, [isSignedIn, refreshCaptureById]);

  const openCapture = useCallback(
    (capture: Capture) => {
      setActionError(null);
      setSelectedCaptureId(capture.id);

      if (capture.status !== 'processing') {
        void refreshCaptureById(capture.id).catch(() => undefined);
      }
    },
    [refreshCaptureById],
  );

  const openCaptureByJobId = useCallback(
    async (jobId: string) => {
      setActionError(null);
      await refreshCaptureById(jobId, { select: true });
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
        const created = await createJob(sourceUrl);
        const capture = captureFromJobCreated(created.job_id, sourceUrl);
        setCaptures((current) => [capture, ...current.filter((item) => item.id !== capture.id)]);
        setSelectedCaptureId(capture.id);
        options.onSuccess?.();
        void refreshCaptureById(created.job_id).catch(() => undefined);
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
        const created = await createJob(capture.sourceUrl);
        const processingCapture = captureFromJobCreated(created.job_id, capture.sourceUrl);
        setCaptures((current) => [
          processingCapture,
          ...current.filter((item) => item.id !== capture.id),
        ]);
        setSelectedCaptureId(processingCapture.id);
        void refreshCaptureById(created.job_id).catch(() => undefined);
      } catch (error) {
        setActionError(errorMessage(error, 'Could not retry this Reel.'));
      } finally {
        setRetryingCaptureId(null);
      }
    },
    [refreshCaptureById],
  );

  const removeBookMention = useCallback(
    async (capture: Capture, bookId: string): Promise<RemoveBookResult> => {
      setActionError(null);
      setRemovingBookId(bookId);

      try {
        await deleteMention(bookId);
        await refreshCaptureById(capture.id);
        return { ok: true };
      } catch (error) {
        const message = errorMessage(error, 'Could not remove this book.');
        setActionError(message);
        return { ok: false, message };
      } finally {
        setRemovingBookId(null);
      }
    },
    [refreshCaptureById],
  );

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
    removingBookId,
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
    openCaptureByJobId,
    submitPasteUrl,
    submitSharedUrl,
    retryCapture,
    removeBookMention,
    openSource,
  };
}
