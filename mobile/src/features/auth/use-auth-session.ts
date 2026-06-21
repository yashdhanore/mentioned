import { useCallback, useEffect, useState } from 'react';

import {
  clearAccessTokenProvider,
  devAccessToken,
  errorMessage,
  isDevAuthEnabled,
  setAccessTokenProvider,
} from '@/api';
import { signInWithApple, signInWithGoogle } from '@/auth-signin';
import { disableRegisteredPushToken } from '@/notifications';
import {
  AuthCanceledError,
  type AuthProvider,
  currentAccessToken,
  isSupabaseConfigured,
  supabase,
} from '@/supabase';

type UseAuthSessionResult = {
  isAuthLoading: boolean;
  isSignedIn: boolean;
  accountLabel: string;
  authError: string | null;
  authProviderInFlight: AuthProvider | null;
  profileError: string | null;
  isSigningOut: boolean;
  isDeletingAccount: boolean;
  setAuthError: (message: string | null) => void;
  setProfileError: (message: string | null) => void;
  handleSignIn: (provider: AuthProvider) => Promise<void>;
  handleSignOut: (registeredPushToken: string | null) => Promise<void>;
  handleDeleteAccount: (
    registeredPushToken: string | null,
    deleteAccount: () => Promise<{ deleted: boolean }>,
  ) => Promise<boolean>;
};

export function useAuthSession(): UseAuthSessionResult {
  const [isAuthLoading, setIsAuthLoading] = useState(true);
  const [isSignedIn, setIsSignedIn] = useState(false);
  const [accountLabel, setAccountLabel] = useState('Signed in');
  const [authError, setAuthError] = useState<string | null>(null);
  const [authProviderInFlight, setAuthProviderInFlight] = useState<AuthProvider | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [isDeletingAccount, setIsDeletingAccount] = useState(false);

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
      return undefined;
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
      if (provider === 'apple') {
        await signInWithApple();
      } else {
        await signInWithGoogle();
      }
    } catch (error) {
      if (error instanceof AuthCanceledError) {
        return;
      }
      setAuthError(errorMessage(error, 'Could not complete sign in.'));
    } finally {
      setAuthProviderInFlight(null);
    }
  }, []);

  const handleSignOut = useCallback(async (registeredPushToken: string | null) => {
    setProfileError(null);
    setIsSigningOut(true);
    try {
      if (isDevAuthEnabled) {
        return;
      }

      await disableRegisteredPushToken(registeredPushToken);
      const { error } = await supabase.auth.signOut();
      if (error) {
        throw error;
      }
    } catch (error) {
      setProfileError(errorMessage(error, 'Could not sign out.'));
    } finally {
      setIsSigningOut(false);
    }
  }, []);

  const handleDeleteAccount = useCallback(
    async (
      registeredPushToken: string | null,
      deleteAccount: () => Promise<{ deleted: boolean }>,
    ) => {
      setProfileError(null);
      setIsDeletingAccount(true);
      try {
        await deleteAccount();
        await disableRegisteredPushToken(registeredPushToken);
        if (!isDevAuthEnabled) {
          await supabase.auth.signOut();
        }
        return true;
      } catch (error) {
        setProfileError(errorMessage(error, 'Could not delete your account.'));
        return false;
      } finally {
        setIsDeletingAccount(false);
      }
    },
    [],
  );

  return {
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
  };
}
