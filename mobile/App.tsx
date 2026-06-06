import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Linking from 'expo-linking';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState, SafeAreaView, useWindowDimensions } from 'react-native';

import {
  clearAccessTokenProvider,
  devAccessToken,
  errorMessage,
  isDevAuthEnabled,
  PRIVACY_POLICY_URL,
  setAccessTokenProvider,
} from '@/api';
import type { BookMention } from '@/captures';
import { PasteSheet, ProfileSheet, ReelMenuSheet, RemoveBookSheet } from '@/components/sheets';
import {
  createPendingSharedSourceStore,
  type PendingSharedSource,
} from '@/features/captures/pending-shared-source';
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

type Sheet = 'profile' | 'paste' | 'reelMenu' | 'removeBook' | null;
type PendingSharedSourceState = PendingSharedSource & {
  shouldAutoSubmit: boolean;
};

const INVALID_SHARED_SOURCE_MESSAGE = 'Share an Instagram Reel or post link to save it.';
const pendingSharedSourceStore = createPendingSharedSourceStore(AsyncStorage);

export default function App() {
  const { width } = useWindowDimensions();
  const contentWidth = Math.min(width, 430);
  const [isAuthLoading, setIsAuthLoading] = useState(true);
  const [isSignedIn, setIsSignedIn] = useState(false);
  const [accountLabel, setAccountLabel] = useState('Signed in');
  const [sheet, setSheet] = useState<Sheet>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [shareLinkError, setShareLinkError] = useState<string | null>(null);
  const [authProviderInFlight, setAuthProviderInFlight] = useState<AuthProvider | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [selectedBook, setSelectedBook] = useState<BookMention | null>(null);
  const [bookRemovalError, setBookRemovalError] = useState<string | null>(null);
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [registeredPushToken, setRegisteredPushToken] = useState<string | null>(null);
  const [pendingSharedSource, setPendingSharedSource] = useState<PendingSharedSourceState | null>(null);
  const handledSharedSourceKeysRef = useRef<Set<string>>(new Set());
  const submittingSharedSourceKeysRef = useRef<Set<string>>(new Set());
  const pendingSharedSourceRef = useRef<PendingSharedSourceState | null>(null);
  const authStateRef = useRef({ isAuthLoading: true, isSignedIn: false });
  const initialShareUrlProcessedRef = useRef(false);

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

  useEffect(() => {
    pendingSharedSourceRef.current = pendingSharedSource;
  }, [pendingSharedSource]);

  useEffect(() => {
    authStateRef.current = { isAuthLoading, isSignedIn };
  }, [isAuthLoading, isSignedIn]);

  useEffect(() => {
    let isMounted = true;

    void pendingSharedSourceStore
      .load()
      .then((source) => {
        if (!isMounted || !source) {
          return;
        }
        setPendingSharedSource((currentSource) => {
          if (currentSource) {
            return currentSource;
          }
          return {
            ...source,
            shouldAutoSubmit: false,
          };
        });
      })
      .catch(() => {
        if (isMounted) {
          setAuthError('Could not restore the shared source.');
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleIncomingShareLink = useCallback(
    (url: string) => {
      const result = parseMentionedShareDeepLink(url);
      if (result.type === 'non-share-link') {
        return;
      }

      if (result.type === 'invalid-share-link') {
        setSelectedCaptureId(null);
        setShareLinkError(INVALID_SHARED_SOURCE_MESSAGE);
        setSharedCaptureError(INVALID_SHARED_SOURCE_MESSAGE);
        setSheet((currentSheet) => (currentSheet === 'paste' ? null : currentSheet));
        return;
      }

      const sourceKey = result.sourceUrl;
      if (
        handledSharedSourceKeysRef.current.has(sourceKey) ||
        submittingSharedSourceKeysRef.current.has(sourceKey)
      ) {
        return;
      }

      clearSharedCaptureError();
      setShareLinkError(null);
      submittingSharedSourceKeysRef.current.add(sourceKey);

      if (!authStateRef.current.isAuthLoading && authStateRef.current.isSignedIn) {
        setPendingSharedSource({
          sourceUrl: result.sourceUrl,
          sourceKey,
          createdAtMs: Date.now(),
          shouldAutoSubmit: true,
        });
        return;
      }

      void pendingSharedSourceStore
        .save(result.sourceUrl)
        .then((source) => {
          submittingSharedSourceKeysRef.current.delete(sourceKey);
          setPendingSharedSource((currentSource) => {
            if (currentSource && currentSource.createdAtMs > source.createdAtMs) {
              return currentSource;
            }
            return {
              ...source,
              shouldAutoSubmit: authStateRef.current.isAuthLoading,
            };
          });
        })
        .catch((error) => {
          submittingSharedSourceKeysRef.current.delete(sourceKey);
          setPendingSharedSource((currentSource) =>
            currentSource ?? {
              sourceUrl: result.sourceUrl,
              sourceKey,
              createdAtMs: Date.now(),
              shouldAutoSubmit: authStateRef.current.isAuthLoading,
            },
          );
          if (!authStateRef.current.isAuthLoading) {
            setAuthError(errorMessage(error, 'Could not keep that shared source. Try sharing it again.'));
          }
        });
    },
    [clearSharedCaptureError, setSelectedCaptureId, setSharedCaptureError],
  );

  useEffect(() => {
    if (isDevAuthEnabled) {
      setAccessTokenProvider(devAccessToken);
      setIsSignedIn(true);
      setAccountLabel('Dev User');
      setIsAuthLoading(false);
      return () => {
        clearAccessTokenProvider();
      };
    }

    if (!isSupabaseConfigured) {
      clearAccessTokenProvider();
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
    if (initialShareUrlProcessedRef.current) {
      return;
    }
    initialShareUrlProcessedRef.current = true;

    let isMounted = true;

    void Linking.getInitialURL()
      .then((url) => {
        if (isMounted && url) {
          handleIncomingShareLink(url);
        }
      })
      .catch(() => undefined);

    return () => {
      isMounted = false;
    };
  }, [handleIncomingShareLink]);

  useEffect(() => {
    const subscription = Linking.addEventListener('url', (event) => {
      handleIncomingShareLink(event.url);
    });

    return () => {
      subscription.remove();
    };
  }, [handleIncomingShareLink]);

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

  const clearPendingSharedSource = useCallback(async (expectedSourceKey?: string) => {
    const currentSource = pendingSharedSourceRef.current;
    if (expectedSourceKey && currentSource?.sourceKey !== expectedSourceKey) {
      return;
    }

    if (currentSource) {
      submittingSharedSourceKeysRef.current.delete(currentSource.sourceKey);
    }
    try {
      if (expectedSourceKey) {
        await pendingSharedSourceStore.clearIfCurrent(expectedSourceKey);
      } else {
        await pendingSharedSourceStore.clear();
      }
    } catch {
      // Local cleanup should not block clearing the in-memory prompt.
    }
    setPendingSharedSource((latestSource) => {
      if (expectedSourceKey && latestSource?.sourceKey !== expectedSourceKey) {
        return latestSource;
      }
      return null;
    });
  }, []);

  const discardPendingSharedSource = useCallback(async () => {
    await clearPendingSharedSource(pendingSharedSourceRef.current?.sourceKey);
    setShareLinkError(null);
    setAuthError(null);
    clearSharedCaptureError();
  }, [clearPendingSharedSource, clearSharedCaptureError]);

  const submitPendingSharedSource = useCallback(async () => {
    const source = pendingSharedSourceRef.current;
    if (!source || !isSignedIn) {
      return;
    }

    const didSubmit = await submitSharedUrl(source.sourceUrl);
    submittingSharedSourceKeysRef.current.delete(source.sourceKey);

    if (pendingSharedSourceRef.current?.sourceKey !== source.sourceKey) {
      return;
    }

    if (didSubmit) {
      handledSharedSourceKeysRef.current.add(source.sourceKey);
      await clearPendingSharedSource(source.sourceKey);
      setShareLinkError(null);
      clearSharedCaptureError();
      setSheet((currentSheet) => (currentSheet === 'paste' ? null : currentSheet));
      return;
    }

    setPendingSharedSource((currentSource) =>
      currentSource?.sourceKey === source.sourceKey
        ? { ...currentSource, shouldAutoSubmit: false }
        : currentSource,
    );
    setSelectedCaptureId(null);
    setSheet((currentSheet) => (currentSheet === 'paste' ? null : currentSheet));
  }, [
    clearPendingSharedSource,
    clearSharedCaptureError,
    isSignedIn,
    setSelectedCaptureId,
    submitSharedUrl,
  ]);

  useEffect(() => {
    if (!pendingSharedSource || isAuthLoading) {
      return;
    }

    if (!isSignedIn) {
      if (pendingSharedSource.shouldAutoSubmit) {
        setPendingSharedSource((currentSource) =>
          currentSource?.sourceKey === pendingSharedSource.sourceKey
            ? { ...currentSource, shouldAutoSubmit: false }
            : currentSource,
        );
      }
      return;
    }

    if (pendingSharedSource.shouldAutoSubmit) {
      void submitPendingSharedSource();
    }
  }, [isAuthLoading, isSignedIn, pendingSharedSource, submitPendingSharedSource]);

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
      if (isDevAuthEnabled) {
        setRegisteredPushToken(null);
        setSheet(null);
        return;
      }

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
    setShareLinkError(null);
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
        pendingSharedSourceUrl={pendingSharedSource?.sourceUrl ?? null}
        isGoogleLoading={authProviderInFlight === 'google'}
        isDisabled={authProviderInFlight !== null}
        onContinueGoogle={() => void handleSignIn('google')}
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
          pendingSharedSourceUrl={pendingSharedSource?.sourceUrl ?? null}
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
