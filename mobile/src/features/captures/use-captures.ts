import { useCallback, useEffect, useMemo, useState } from 'react';
import { Linking } from 'react-native';

import { createJob, errorMessage, getJob, listAllJobs } from '@/api';
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

type UseCapturesResult = {
  captures: Capture[];
  selectedCapture: Capture | null;
  pasteUrl: string;
  isLoadingCaptures: boolean;
  isSubmittingUrl: boolean;
  retryingCaptureId: string | null;
  loadError: string | null;
  pasteError: string | null;
  actionError: string | null;
  setSelectedCaptureId: (captureId: string | null) => void;
  setPasteUrl: (url: string) => void;
  clearPasteError: () => void;
  refreshCaptures: (options?: { silent?: boolean }) => Promise<void>;
  openCapture: (capture: Capture) => void;
  openCaptureByJobId: (jobId: string) => Promise<void>;
  submitPasteUrl: () => Promise<boolean>;
  retryCapture: (capture: Capture) => Promise<void>;
  openSource: (capture: Capture) => Promise<void>;
};

export function useCaptures(isSignedIn: boolean): UseCapturesResult {
  const [captures, setCaptures] = useState<Capture[]>([]);
  const [selectedCaptureId, setSelectedCaptureId] = useState<string | null>(null);
  const [pasteUrl, setPasteUrlState] = useState('');
  const [isLoadingCaptures, setIsLoadingCaptures] = useState(false);
  const [isSubmittingUrl, setIsSubmittingUrl] = useState(false);
  const [retryingCaptureId, setRetryingCaptureId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pasteError, setPasteError] = useState<string | null>(null);
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
        setLoadError(errorMessage(error, 'Could not load saved Reels.'));
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

  const submitPasteUrl = useCallback(async () => {
    const url = pasteUrl.trim();
    if (!url) {
      setPasteError('Paste an Instagram Reel or post URL.');
      return false;
    }

    setPasteError(null);
    setIsSubmittingUrl(true);

    try {
      const created = await createJob(url);
      const capture = captureFromJobCreated(created.job_id, url);
      setCaptures((current) => [capture, ...current.filter((item) => item.id !== capture.id)]);
      setSelectedCaptureId(capture.id);
      setPasteUrlState('');
      void refreshCaptureById(created.job_id).catch(() => undefined);
      return true;
    } catch (error) {
      setPasteError(errorMessage(error, 'Could not submit that Reel.'));
      return false;
    } finally {
      setIsSubmittingUrl(false);
    }
  }, [pasteUrl, refreshCaptureById]);

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

  const openSource = useCallback(async (capture: Capture) => {
    setActionError(null);
    if (!isAllowedInstagramUrl(capture.sourceUrl)) {
      setActionError('This source URL cannot be opened from the app.');
      return;
    }
    try {
      await Linking.openURL(capture.sourceUrl);
    } catch (error) {
      setActionError(errorMessage(error, 'Could not open the source URL.'));
    }
  }, []);

  return {
    captures,
    selectedCapture,
    pasteUrl,
    isLoadingCaptures,
    isSubmittingUrl,
    retryingCaptureId,
    loadError,
    pasteError,
    actionError,
    setSelectedCaptureId,
    setPasteUrl,
    clearPasteError,
    refreshCaptures,
    openCapture,
    openCaptureByJobId,
    submitPasteUrl,
    retryCapture,
    openSource,
  };
}
