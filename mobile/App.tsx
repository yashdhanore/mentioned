import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useState } from 'react';
import { BackHandler, SafeAreaView, useWindowDimensions } from 'react-native';

import { deleteAccount, PRIVACY_POLICY_URL } from '@/api';
import { PasteSheet, ProfileSheet, ReelMenuSheet } from '@/components/sheets';
import { useCaptures } from '@/features/captures/use-captures';
import { useSharedSourceIntake } from '@/features/captures/use-shared-source-intake';
import { useAuthSession } from '@/features/auth/use-auth-session';
import { useNotificationRouting } from '@/features/notifications/use-notification-routing';
import { AuthLoadingScreen } from '@/screens/auth-loading-screen';
import { HomeScreen } from '@/screens/home-screen';
import { ReelDetailScreen } from '@/screens/reel-detail-screen';
import { SignedOutScreen } from '@/screens/signed-out-screen';
import { maxContentWidth, spacing } from '@/theme';
import { styles } from '@/styles';

type Sheet = 'profile' | 'paste' | 'reelMenu' | null;

export default function App() {
  const { width } = useWindowDimensions();
  const contentWidth = Math.min(width, maxContentWidth);
  const {
    isAuthLoading,
    isSignedIn,
    accountLabel,
    authError,
    authProviderInFlight,
    profileError,
    isSigningOut,
    isDeletingAccount,
    setAuthError,
    setProfileError,
    handleSignIn,
    handleSignOut,
    handleDeleteAccount,
  } = useAuthSession();
  const [sheet, setSheet] = useState<Sheet>(null);
  const [confirmingDeleteAccount, setConfirmingDeleteAccount] = useState(false);

  const {
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
  } = useCaptures(isSignedIn);

  const tileWidth = (contentWidth - spacing.screen * 2 - spacing.md) / 2;

  const closePasteSheet = useCallback(() => {
    clearPasteError();
    setSheet(null);
  }, [clearPasteError]);

  const {
    pendingSharedSourceUrl,
    shareLinkError,
    submitPendingSharedSource,
    discardPendingSharedSource,
  } = useSharedSourceIntake({
    isAuthLoading,
    isSignedIn,
    submitSharedUrl,
    setSelectedCaptureId,
    setSharedCaptureError,
    clearSharedCaptureError,
    setAuthError,
    closePasteSheet,
  });

  const { registeredPushToken, clearRegisteredPushToken } = useNotificationRouting({
    isSignedIn,
    refreshCaptures,
    openCaptureBySavedSourceId,
  });

  const signOutAndClose = useCallback(async () => {
    const didSignOut = await handleSignOut(registeredPushToken);
    if (!didSignOut) {
      return;
    }
    clearRegisteredPushToken();
    setSheet(null);
  }, [clearRegisteredPushToken, handleSignOut, registeredPushToken]);

  const deleteAccountAndClose = useCallback(async () => {
    const didDelete = await handleDeleteAccount(registeredPushToken, deleteAccount);
    if (!didDelete) {
      return;
    }
    clearRegisteredPushToken();
    setConfirmingDeleteAccount(false);
    setSheet(null);
  }, [clearRegisteredPushToken, handleDeleteAccount, registeredPushToken]);

  const closeProfileSheet = useCallback(() => {
    setProfileError(null);
    setConfirmingDeleteAccount(false);
    setSheet(null);
  }, [setProfileError]);

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

  const deleteSelectedCapture = useCallback(async () => {
    if (!selectedCapture) {
      return;
    }

    const result = await deleteCapture(selectedCapture);
    if (result.ok) {
      setSheet(null);
    }
  }, [deleteCapture, selectedCapture]);

  useEffect(() => {
    const subscription = BackHandler.addEventListener('hardwareBackPress', () => {
      if (sheet === 'profile') {
        closeProfileSheet();
        return true;
      }
      if (sheet === 'paste') {
        closePasteSheet();
        return true;
      }
      if (sheet === 'reelMenu') {
        setSheet(null);
        return true;
      }
      if (selectedCapture) {
        setSelectedCaptureId(null);
        return true;
      }
      return false;
    });

    return () => subscription.remove();
  }, [sheet, selectedCapture, closeProfileSheet, closePasteSheet, setSelectedCaptureId]);

  if (isAuthLoading) {
    return <AuthLoadingScreen />;
  }

  if (!isSignedIn) {
    return (
      <SignedOutScreen
        error={shareLinkError ?? authError}
        pendingSharedSourceUrl={pendingSharedSourceUrl}
        isAppleLoading={authProviderInFlight === 'apple'}
        isDisabled={authProviderInFlight !== null}
        onContinueGoogle={() => void handleSignIn('google')}
        onContinueApple={() => void handleSignIn('apple')}
        onDiscardPendingSharedSource={() => void discardPendingSharedSource()}
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
          pendingSharedSourceUrl={pendingSharedSourceUrl}
          isSubmittingPendingSharedSource={isSubmittingSharedUrl}
          onSavePendingSharedSource={() => void submitPendingSharedSource()}
          onDiscardPendingSharedSource={() => void discardPendingSharedSource()}
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
        isDeletingAccount={isDeletingAccount}
        confirmingDeleteAccount={confirmingDeleteAccount}
        onClose={closeProfileSheet}
        onSignOut={() => void signOutAndClose()}
        onRequestDeleteAccount={() => setConfirmingDeleteAccount(true)}
        onConfirmDeleteAccount={() => void deleteAccountAndClose()}
        onCancelDeleteAccount={() => setConfirmingDeleteAccount(false)}
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
        error={sheet === 'reelMenu' ? actionError : null}
        isDeleting={selectedCapture ? deletingCaptureId === selectedCapture.id : false}
        onClose={() => setSheet(null)}
        onDeletePost={selectedCapture ? () => void deleteSelectedCapture() : undefined}
        onOpenSource={selectedCapture ? () => void openSource(selectedCapture) : undefined}
      />
    </SafeAreaView>
  );
}
