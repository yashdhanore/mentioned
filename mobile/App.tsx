import * as Linking from 'expo-linking';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState, SafeAreaView, useWindowDimensions } from 'react-native';

import { clearAccessTokenProvider, errorMessage, PRIVACY_POLICY_URL, setAccessTokenProvider } from '@/api';
import { PasteSheet, ProfileSheet, ReelMenuSheet } from '@/components/sheets';
import { useCaptures } from '@/features/captures/use-captures';
import {
  addNotificationTapListener,
  addPushTokenRegistrationListener,
  clearLastNotificationResponse,
  disableRegisteredPushToken,
  getLastNotificationJobId,
  registerForPushNotificationsAsync,
} from '@/notifications';
import { AuthLoadingScreen } from '@/screens/auth-loading-screen';
import { HomeScreen } from '@/screens/home-screen';
import { ReelDetailScreen } from '@/screens/reel-detail-screen';
import { SignedOutScreen } from '@/screens/signed-out-screen';
import { type AuthProvider, currentAccessToken, isSupabaseConfigured, signInWithProvider, supabase } from '@/supabase';
import { parseMentionedShareDeepLink } from '@/utils/shared-source-url';
import { spacing } from '@/theme';
import { styles } from '@/styles';

type Sheet = 'profile' | 'paste' | 'reelMenu' | null;
type PendingSharedSource = { rawUrl: string; sourceUrl: string };

export default function App() {
  const { width } = useWindowDimensions();
  const contentWidth = Math.min(width, 430);
  const [isAuthLoading, setIsAuthLoading] = useState(true);
  const [isSignedIn, setIsSignedIn] = useState(false);
  const [accountLabel, setAccountLabel] = useState('Signed in');
  const [sheet, setSheet] = useState<Sheet>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [authProviderInFlight, setAuthProviderInFlight] = useState<AuthProvider | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [registeredPushToken, setRegisteredPushToken] = useState<string | null>(null);
  const [pendingSharedSource, setPendingSharedSource] = useState<PendingSharedSource | null>(null);
  const pendingSharedSourceRef = useRef<PendingSharedSource | null>(null);
  const handledShareDeepLinksRef = useRef<Set<string>>(new Set());
  const submittingShareDeepLinksRef = useRef<Set<string>>(new Set());

  const {
    captures,
    selectedCapture,
    pasteUrl,
    isLoadingCaptures,
    isSubmittingUrl,
    retryingCaptureId,
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
    openSource,
  } = useCaptures(isSignedIn);

  const tileWidth = (contentWidth - spacing.screen * 2 - spacing.md) / 2;

  const handleIncomingShareLink = useCallback(
    (url: string) => {
      const result = parseMentionedShareDeepLink(url);
      if (result.type === 'non-share-link') {
        return;
      }

      if (handledShareDeepLinksRef.current.has(url) || submittingShareDeepLinksRef.current.has(url)) {
        return;
      }

      if (result.type === 'invalid-share-link') {
        setSelectedCaptureId(null);
        setSharedCaptureError('Share an Instagram Reel or post link to save it.');
        setSheet((currentSheet) => (currentSheet === 'paste' ? null : currentSheet));
        return;
      }

      clearSharedCaptureError();
      if (pendingSharedSourceRef.current) {
        return;
      }

      const pendingSource = { rawUrl: url, sourceUrl: result.sourceUrl };
      pendingSharedSourceRef.current = pendingSource;
      submittingShareDeepLinksRef.current.add(url);
      setPendingSharedSource(pendingSource);
    },
    [clearSharedCaptureError, setSelectedCaptureId, setSharedCaptureError],
  );

  useEffect(() => {
    if (!isSupabaseConfigured) {
      setIsSignedIn(true);
      setAccountLabel('Dev User');
      setIsAuthLoading(false);
      return;
    }

    setAccessTokenProvider(currentAccessToken);
    let isMounted = true;

    void supabase.auth
      .getSession()
      .then(({ data }) => {
        if (!isMounted) {
          return;
        }
        setIsSignedIn(Boolean(data.session));
        setAccountLabel(data.session?.user.email || 'Signed in');
      })
      .catch(() => {
        if (!isMounted) {
          return;
        }
        setIsSignedIn(false);
        setAuthError('Could not restore your sign-in session.');
      })
      .finally(() => {
        if (isMounted) {
          setIsAuthLoading(false);
        }
      });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setIsSignedIn(Boolean(session));
      setAccountLabel(session?.user.email || 'Signed in');
      if (session) {
        setAuthError(null);
      } else {
        setRegisteredPushToken(null);
      }
    });

    return () => {
      isMounted = false;
      subscription.unsubscribe();
      clearAccessTokenProvider();
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    void Linking.getInitialURL()
      .then((url) => {
        if (isMounted && url) {
          handleIncomingShareLink(url);
        }
      })
      .catch(() => undefined);

    const subscription = Linking.addEventListener('url', (event) => {
      handleIncomingShareLink(event.url);
    });

    return () => {
      isMounted = false;
      subscription.remove();
    };
  }, [handleIncomingShareLink]);

  useEffect(() => {
    if (!pendingSharedSource || isAuthLoading) {
      return undefined;
    }

    if (!isSignedIn) {
      setAuthError('Sign in to save shared Instagram links.');
      return undefined;
    }

    let isMounted = true;
    const { rawUrl, sourceUrl } = pendingSharedSource;
    void submitSharedUrl(sourceUrl).then((didSubmit) => {
      if (!isMounted) {
        return;
      }

      submittingShareDeepLinksRef.current.delete(rawUrl);
      if (pendingSharedSourceRef.current?.rawUrl === rawUrl) {
        pendingSharedSourceRef.current = null;
        setPendingSharedSource(null);
      }

      if (didSubmit) {
        handledShareDeepLinksRef.current.add(rawUrl);
        clearSharedCaptureError();
        setSheet((currentSheet) => (currentSheet === 'paste' ? null : currentSheet));
      } else {
        setSelectedCaptureId(null);
        setSheet((currentSheet) => (currentSheet === 'paste' ? null : currentSheet));
      }
    });

    return () => {
      isMounted = false;
    };
  }, [
    clearSharedCaptureError,
    isAuthLoading,
    isSignedIn,
    pendingSharedSource,
    setSelectedCaptureId,
    submitSharedUrl,
  ]);

  useEffect(() => {
    if (!isSignedIn) {
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

  const handleSignIn = useCallback(async (provider: AuthProvider) => {
    setAuthError(null);
    setAuthProviderInFlight(provider);
    try {
      await signInWithProvider(provider);
    } catch (error) {
      setAuthError(errorMessage(error, 'Could not complete sign in.'));
    } finally {
      setAuthProviderInFlight(null);
    }
  }, []);

  const handleSignOut = useCallback(async () => {
    setProfileError(null);
    setIsSigningOut(true);
    try {
      await disableRegisteredPushToken(registeredPushToken);
      const { error } = await supabase.auth.signOut();
      if (error) {
        throw error;
      }
      setRegisteredPushToken(null);
      setSheet(null);
    } catch (error) {
      setProfileError(errorMessage(error, 'Could not sign out.'));
    } finally {
      setIsSigningOut(false);
    }
  }, [registeredPushToken]);

  const closePasteSheet = useCallback(() => {
    clearPasteError();
    setSheet(null);
  }, [clearPasteError]);

  const openPasteSheet = useCallback(() => {
    clearSharedCaptureError();
    setSheet('paste');
  }, [clearSharedCaptureError]);

  const submitPasteAndCloseOnSuccess = useCallback(async () => {
    const didSubmit = await submitPasteUrl();
    if (didSubmit) {
      setSheet(null);
    }
  }, [submitPasteUrl]);

  if (isAuthLoading) {
    return <AuthLoadingScreen />;
  }

  if (!isSignedIn) {
    return (
      <SignedOutScreen
        error={authError}
        isGoogleLoading={authProviderInFlight === 'google'}
        isDisabled={authProviderInFlight !== null}
        onContinueGoogle={() => void handleSignIn('google')}
        privacyPolicyUrl={PRIVACY_POLICY_URL}
      />
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      {selectedCapture ? (
        <ReelDetailScreen
          capture={selectedCapture}
          width={contentWidth}
          actionError={actionError}
          isRetrying={retryingCaptureId === selectedCapture.id}
          onBack={() => setSelectedCaptureId(null)}
          onOpenMenu={() => setSheet('reelMenu')}
          onOpenSource={() => void openSource(selectedCapture)}
          onRetry={() => void retryCapture(selectedCapture)}
        />
      ) : (
        <HomeScreen
          captures={captures}
          error={sharedCaptureError ?? loadError}
          errorActionLabel={sharedCaptureError ? undefined : 'Try again'}
          onErrorAction={sharedCaptureError ? undefined : () => void refreshCaptures()}
          isLoading={isLoadingCaptures}
          tileWidth={tileWidth}
          onOpenPaste={openPasteSheet}
          onOpenProfile={() => setSheet('profile')}
          onOpenCapture={openCapture}
        />
      )}

      <ProfileSheet
        visible={sheet === 'profile'}
        accountLabel={accountLabel}
        error={profileError}
        isSigningOut={isSigningOut}
        onClose={() => setSheet(null)}
        onSignOut={() => void handleSignOut()}
        privacyPolicyUrl={PRIVACY_POLICY_URL}
      />
      <PasteSheet
        visible={sheet === 'paste'}
        error={pasteError}
        isSubmitting={isSubmittingUrl}
        value={pasteUrl}
        onChange={setPasteUrl}
        onClose={closePasteSheet}
        onSubmit={() => void submitPasteAndCloseOnSuccess()}
      />
      <ReelMenuSheet
        visible={sheet === 'reelMenu'}
        onClose={() => setSheet(null)}
        onOpenSource={selectedCapture ? () => void openSource(selectedCapture) : undefined}
      />
    </SafeAreaView>
  );
}
