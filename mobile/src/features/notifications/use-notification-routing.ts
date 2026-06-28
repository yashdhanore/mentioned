import { useEffect, useState } from 'react';
import { AppState } from 'react-native';

import {
  addNotificationTapListener,
  addPushTokenRegistrationListener,
  clearLastNotificationResponse,
  getLastNotificationSavedSourceId,
  registerForPushNotificationsAsync,
} from '@/notifications';

type UseNotificationRoutingOptions = {
  isSignedIn: boolean;
  refreshCaptures: (options?: { silent?: boolean }) => Promise<void>;
  openCaptureBySavedSourceId: (savedSourceId: string) => Promise<void>;
};

type UseNotificationRoutingResult = {
  registeredPushToken: string | null;
  clearRegisteredPushToken: () => void;
};

export function useNotificationRouting({
  isSignedIn,
  refreshCaptures,
  openCaptureBySavedSourceId,
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
    const openSavedSourceFromNotification = (savedSourceId: string) => {
      void openCaptureBySavedSourceId(savedSourceId)
        .catch(() => undefined)
        .finally(() => {
          void clearLastNotificationResponse().catch(() => undefined);
        });
    };

    void getLastNotificationSavedSourceId()
      .then((savedSourceId) => {
        if (isMounted && savedSourceId) {
          openSavedSourceFromNotification(savedSourceId);
        }
      })
      .catch(() => undefined);

    const subscription = addNotificationTapListener((savedSourceId) => {
      if (isMounted) {
        openSavedSourceFromNotification(savedSourceId);
      }
    });

    return () => {
      isMounted = false;
      subscription.remove();
    };
  }, [isSignedIn, openCaptureBySavedSourceId]);

  return {
    registeredPushToken,
    clearRegisteredPushToken: () => setRegisteredPushToken(null),
  };
}
