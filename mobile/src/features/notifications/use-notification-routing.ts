import { useEffect, useState } from 'react';
import { AppState } from 'react-native';

import {
  addNotificationTapListener,
  addPushTokenRegistrationListener,
  clearLastNotificationResponse,
  getLastNotificationJobId,
  registerForPushNotificationsAsync,
} from '@/notifications';

type UseNotificationRoutingOptions = {
  isSignedIn: boolean;
  refreshCaptures: (options?: { silent?: boolean }) => Promise<void>;
  openCaptureByJobId: (jobId: string) => Promise<void>;
};

type UseNotificationRoutingResult = {
  registeredPushToken: string | null;
  clearRegisteredPushToken: () => void;
};

export function useNotificationRouting({
  isSignedIn,
  refreshCaptures,
  openCaptureByJobId,
}: UseNotificationRoutingOptions): UseNotificationRoutingResult {
  const [registeredPushToken, setRegisteredPushToken] = useState<string | null>(null);

  useEffect(() => {
    if (!isSignedIn) {
      setRegisteredPushToken(null);
      return undefined;
    }

    let isMounted = true;
    void registerForPushNotificationsAsync().then((expoPushToken) => {
      if (isMounted && expoPushToken) {
        setRegisteredPushToken(expoPushToken);
      }
    });

    const subscription = addPushTokenRegistrationListener((expoPushToken) => {
      if (isMounted) {
        setRegisteredPushToken(expoPushToken);
      }
    });

    return () => {
      isMounted = false;
      subscription?.remove();
    };
  }, [isSignedIn]);

  useEffect(() => {
    if (!isSignedIn) {
      return undefined;
    }

    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') {
        void refreshCaptures({ silent: true });
      }
    });

    return () => {
      subscription.remove();
    };
  }, [isSignedIn, refreshCaptures]);

  useEffect(() => {
    if (!isSignedIn) {
      return undefined;
    }

    let isMounted = true;
    const openJobFromNotification = (jobId: string) => {
      void openCaptureByJobId(jobId)
        .catch(() => undefined)
        .finally(() => {
          void clearLastNotificationResponse().catch(() => undefined);
        });
    };

    void getLastNotificationJobId()
      .then((jobId) => {
        if (isMounted && jobId) {
          openJobFromNotification(jobId);
        }
      })
      .catch(() => undefined);

    const subscription = addNotificationTapListener((jobId) => {
      if (isMounted) {
        openJobFromNotification(jobId);
      }
    });

    return () => {
      isMounted = false;
      subscription.remove();
    };
  }, [isSignedIn, openCaptureByJobId]);

  return {
    registeredPushToken,
    clearRegisteredPushToken: () => setRegisteredPushToken(null),
  };
}
