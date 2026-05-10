import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useState } from 'react';
import { SafeAreaView, useWindowDimensions } from 'react-native';

import { clearAccessTokenProvider, errorMessage, setAccessTokenProvider } from '@/api';
import { PasteSheet, ProfileSheet, ReelMenuSheet } from '@/components/sheets';
import { useCaptures } from '@/features/captures/use-captures';
import { AuthLoadingScreen } from '@/screens/auth-loading-screen';
import { HomeScreen } from '@/screens/home-screen';
import { ReelDetailScreen } from '@/screens/reel-detail-screen';
import { SignedOutScreen } from '@/screens/signed-out-screen';
import { type AuthProvider, currentAccessToken, isSupabaseConfigured, signInWithProvider, supabase } from '@/supabase';
import { spacing } from '@/theme';
import { styles } from '@/styles';

type Sheet = 'profile' | 'paste' | 'reelMenu' | null;

export default function App() {
  const { width } = useWindowDimensions();
  const [isAuthLoading, setIsAuthLoading] = useState(true);
  const [isSignedIn, setIsSignedIn] = useState(false);
  const [accountLabel, setAccountLabel] = useState('Signed in');
  const [sheet, setSheet] = useState<Sheet>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [authProviderInFlight, setAuthProviderInFlight] = useState<AuthProvider | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [isSigningOut, setIsSigningOut] = useState(false);

  const {
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
    submitPasteUrl,
    retryCapture,
    openSource,
  } = useCaptures(isSignedIn);

  const tileWidth = (width - spacing.screen * 2 - spacing.md) / 2;

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
      }
    });

    return () => {
      isMounted = false;
      subscription.unsubscribe();
      clearAccessTokenProvider();
    };
  }, []);

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
      const { error } = await supabase.auth.signOut();
      if (error) {
        throw error;
      }
      setSheet(null);
    } catch (error) {
      setProfileError(errorMessage(error, 'Could not sign out.'));
    } finally {
      setIsSigningOut(false);
    }
  }, []);

  const closePasteSheet = useCallback(() => {
    clearPasteError();
    setSheet(null);
  }, [clearPasteError]);

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
        isAppleLoading={authProviderInFlight === 'apple'}
        isGoogleLoading={authProviderInFlight === 'google'}
        isDisabled={authProviderInFlight !== null}
        onContinueApple={() => void handleSignIn('apple')}
        onContinueGoogle={() => void handleSignIn('google')}
      />
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      {selectedCapture ? (
        <ReelDetailScreen
          capture={selectedCapture}
          width={width}
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
          error={loadError}
          isLoading={isLoadingCaptures}
          tileWidth={tileWidth}
          onOpenPaste={() => setSheet('paste')}
          onOpenProfile={() => setSheet('profile')}
          onOpenCapture={openCapture}
          onRefresh={() => void refreshCaptures()}
        />
      )}

      <ProfileSheet
        visible={sheet === 'profile'}
        accountLabel={accountLabel}
        error={profileError}
        isSigningOut={isSigningOut}
        onClose={() => setSheet(null)}
        onSignOut={() => void handleSignOut()}
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
