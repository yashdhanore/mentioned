import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useState } from 'react';
import { AppState, SafeAreaView, useWindowDimensions } from 'react-native';

import {
  deleteAccount,
  PRIVACY_POLICY_URL,
} from '@/api';
import type { BookMention } from '@/captures';
import { PasteSheet, ProfileSheet, ReelMenuSheet, RemoveBookSheet } from '@/components/sheets';
import { useCaptures } from '@/features/captures/use-captures';
import { useSharedSourceIntake } from '@/features/captures/use-shared-source-intake';
import { useAuthSession } from '@/features/auth/use-auth-session';
import {
  addNotificationTapListener,
  addPushTokenRegistrationListener,
  clearLastNotificationResponse,
  getLastNotificationJobId,
  registerForPushNotificationsAsync,
} from '@/notifications';
import { AuthLoadingScreen } from '@/screens/auth-loading-screen';
import { HomeScreen } from '@/screens/home-screen';
import { ReelDetailScreen } from '@/screens/reel-detail-screen';
import { SignedOutScreen } from '@/screens/signed-out-screen';
import { spacing } from '@/theme';
import { styles } from '@/styles';

type Sheet = 'profile' | 'paste' | 'reelMenu' | 'removeBook' | null;

export default function App() {
  const { width } = useWindowDimensions();
  const contentWidth = Math.min(width, 430);
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
  const [selectedBook, setSelectedBook] = useState<BookMention | null>(null);
  const [bookRemovalError, setBookRemovalError] = useState<string | null>(null);
  const [confirmingDeleteAccount, setConfirmingDeleteAccount] = useState(false);
  const [registeredPushToken, setRegisteredPushToken] = useState<string | null>(null);

  const {
    captures,
    selectedCapture,
    pasteUrl,
    isLoadingCaptures,
    isSubmittingUrl,
    isSubmittingSharedUrl,
    retryingCaptureId,
    removingBookId,
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
    openCaptureByJobId,
    submitPasteUrl,
    submitSharedUrl,
    retryCapture,
    removeBookMention,
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

  const signOutAndClose = useCallback(async () => {
    await handleSignOut(registeredPushToken);
    setRegisteredPushToken(null);
    setSheet(null);
  }, [handleSignOut, registeredPushToken]);

  const deleteAccountAndClose = useCallback(async () => {
    const didDelete = await handleDeleteAccount(registeredPushToken, deleteAccount);
    if (!didDelete) {
      return;
    }
    setRegisteredPushToken(null);
    setConfirmingDeleteAccount(false);
    setSheet(null);
  }, [handleDeleteAccount, registeredPushToken]);

  const closeProfileSheet = useCallback(() => {
    setProfileError(null);
    setConfirmingDeleteAccount(false);
    setSheet(null);
  }, []);

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

  const openRemoveBook = useCallback((book: BookMention) => {
    setSelectedBook(book);
    setBookRemovalError(null);
    setSheet('removeBook');
  }, []);

  const closeRemoveBookSheet = useCallback(() => {
    setBookRemovalError(null);
    setSelectedBook(null);
    setSheet((currentSheet) => (currentSheet === 'removeBook' ? null : currentSheet));
  }, []);

  const removeSelectedBook = useCallback(async () => {
    if (!selectedCapture || !selectedBook) {
      return;
    }

    setBookRemovalError(null);
    const result = await removeBookMention(selectedCapture, selectedBook.id);
    if (result.ok) {
      closeRemoveBookSheet();
      return;
    }
    setBookRemovalError(result.message);
  }, [closeRemoveBookSheet, removeBookMention, selectedBook, selectedCapture]);

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
    if (!selectedBook) {
      return;
    }

    const selectedBookStillExists = selectedCapture?.books.some((book) => book.id === selectedBook.id);
    if (!selectedBookStillExists) {
      closeRemoveBookSheet();
    }
  }, [closeRemoveBookSheet, selectedBook, selectedCapture]);

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
          removingBookId={removingBookId}
          onBack={() => setSelectedCaptureId(null)}
          onOpenMenu={() => setSheet('reelMenu')}
          onOpenRemoveBook={openRemoveBook}
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
      <RemoveBookSheet
        visible={sheet === 'removeBook'}
        book={selectedBook}
        error={bookRemovalError}
        isRemoving={selectedBook ? removingBookId === selectedBook.id : false}
        onClose={closeRemoveBookSheet}
        onRemove={() => void removeSelectedBook()}
      />
    </SafeAreaView>
  );
}
