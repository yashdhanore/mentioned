import Constants from 'expo-constants';
import * as Notifications from 'expo-notifications';

import { disablePushToken, registerPushToken, type PushPlatform } from '@/api';

const JOB_STATUS_CHANNEL_ID = 'job-status';

type EASExtra = {
  eas?: {
    projectId?: string;
  };
};

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});

function devicePlatform(): PushPlatform | null {
  if (process.env.EXPO_OS === 'ios') {
    return 'ios';
  }
  if (process.env.EXPO_OS === 'android') {
    return 'android';
  }
  return null;
}

function resolveProjectId(): string | null {
  const envProjectId = process.env.EXPO_PUBLIC_EAS_PROJECT_ID?.trim();
  if (envProjectId) {
    return envProjectId;
  }

  const extra = Constants.expoConfig?.extra as EASExtra | undefined;
  return extra?.eas?.projectId || Constants.easConfig?.projectId || null;
}

function allowsNotifications(settings: Notifications.NotificationPermissionsStatus): boolean {
  if (settings.granted) {
    return true;
  }

  const iosStatus = settings.ios?.status;
  return (
    iosStatus === Notifications.IosAuthorizationStatus.AUTHORIZED ||
    iosStatus === Notifications.IosAuthorizationStatus.PROVISIONAL ||
    iosStatus === Notifications.IosAuthorizationStatus.EPHEMERAL
  );
}

async function ensureAndroidChannel(): Promise<void> {
  if (process.env.EXPO_OS !== 'android') {
    return;
  }

  await Notifications.setNotificationChannelAsync(JOB_STATUS_CHANNEL_ID, {
    name: 'Job status',
    description: 'Updates when a Reel has finished processing.',
    importance: Notifications.AndroidImportance.DEFAULT,
    vibrationPattern: [0, 250],
    lightColor: '#345D8C',
  });
}

async function ensureNotificationPermission(): Promise<boolean> {
  await ensureAndroidChannel();

  const existing = await Notifications.getPermissionsAsync();
  if (allowsNotifications(existing)) {
    return true;
  }

  const requested = await Notifications.requestPermissionsAsync({
    ios: {
      allowAlert: true,
      allowBadge: false,
      allowSound: false,
    },
  });
  return allowsNotifications(requested);
}

async function registerExpoPushToken(
  platform: PushPlatform,
  devicePushToken?: Notifications.DevicePushToken,
): Promise<string | null> {
  const projectId = resolveProjectId();
  if (!projectId) {
    if (__DEV__) {
      console.warn('[notifications] Missing EXPO_PUBLIC_EAS_PROJECT_ID.');
    }
    return null;
  }

  try {
    const expoPushToken = (
      await Notifications.getExpoPushTokenAsync({
        projectId,
        ...(devicePushToken ? { devicePushToken } : {}),
      })
    ).data;
    await registerPushToken(expoPushToken, platform);
    return expoPushToken;
  } catch (error) {
    if (__DEV__) {
      console.warn('[notifications] Could not register push token.', error);
    }
    return null;
  }
}

export async function registerForPushNotificationsAsync(): Promise<string | null> {
  const platform = devicePlatform();
  if (!platform) {
    return null;
  }

  if (!resolveProjectId()) {
    if (__DEV__) {
      console.warn('[notifications] Missing EXPO_PUBLIC_EAS_PROJECT_ID.');
    }
    return null;
  }

  const didGrantPermission = await ensureNotificationPermission();
  if (!didGrantPermission) {
    return null;
  }

  return registerExpoPushToken(platform);
}

export function addPushTokenRegistrationListener(
  onRegistered?: (expoPushToken: string) => void,
): Notifications.EventSubscription | null {
  const platform = devicePlatform();
  if (!platform) {
    return null;
  }

  return Notifications.addPushTokenListener((devicePushToken) => {
    void registerExpoPushToken(platform, devicePushToken).then((expoPushToken) => {
      if (expoPushToken) {
        onRegistered?.(expoPushToken);
      }
    });
  });
}

export async function disableRegisteredPushToken(expoPushToken: string | null): Promise<void> {
  if (!expoPushToken) {
    return;
  }

  try {
    await disablePushToken(expoPushToken);
  } catch (error) {
    if (__DEV__) {
      console.warn('[notifications] Could not disable push token.', error);
    }
  }
}

function notificationDataId(
  data: Record<string, unknown> | undefined,
  key: string,
): string | null {
  const value = data?.[key];
  return typeof value === 'string' && value.trim() ? value : null;
}

export function savedSourceIdFromNotificationResponse(
  response: Notifications.NotificationResponse | null,
): string | null {
  if (!response || response.actionIdentifier !== Notifications.DEFAULT_ACTION_IDENTIFIER) {
    return null;
  }

  const data = response.notification.request.content.data;
  return notificationDataId(data, 'saved_source_id');
}

export async function getLastNotificationSavedSourceId(): Promise<string | null> {
  const response = await Notifications.getLastNotificationResponseAsync();
  return savedSourceIdFromNotificationResponse(response);
}

export async function clearLastNotificationResponse(): Promise<void> {
  await Notifications.clearLastNotificationResponseAsync();
}

export function addNotificationTapListener(
  onSavedSourceNotification: (savedSourceId: string) => void,
): Notifications.EventSubscription {
  return Notifications.addNotificationResponseReceivedListener((response) => {
    const savedSourceId = savedSourceIdFromNotificationResponse(response);
    if (savedSourceId) {
      onSavedSourceNotification(savedSourceId);
    }
  });
}
