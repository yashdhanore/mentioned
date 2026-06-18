import * as Linking from 'expo-linking';
import * as WebBrowser from 'expo-web-browser';

import {
  AuthCanceledError,
  type AuthProvider,
  assertSupabaseConfigured,
  supabase,
} from '@/supabase';

WebBrowser.maybeCompleteAuthSession();

const AUTH_CALLBACK_PATH = 'auth/callback';
const authRedirectUrlOverride = process.env.EXPO_PUBLIC_AUTH_REDIRECT_URL?.trim() || '';

function authRedirectUrl(): string {
  if (authRedirectUrlOverride) {
    return authRedirectUrlOverride;
  }

  return Linking.createURL(AUTH_CALLBACK_PATH, { scheme: 'mentioned' });
}

function authErrorFromCallback(callbackUrl: string): string | null {
  const parsed = new URL(callbackUrl);
  return parsed.searchParams.get('error_description') || parsed.searchParams.get('error');
}

async function signInWithProvider(provider: AuthProvider): Promise<void> {
  assertSupabaseConfigured();

  const redirectTo = authRedirectUrl();
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider,
    options: {
      redirectTo,
      skipBrowserRedirect: true,
    },
  });

  if (error) {
    throw error;
  }
  if (!data.url) {
    throw new Error('Supabase did not return an OAuth URL.');
  }

  const result = await WebBrowser.openAuthSessionAsync(data.url, redirectTo);
  if (result.type !== 'success') {
    throw new AuthCanceledError();
  }

  const callbackError = authErrorFromCallback(result.url);
  if (callbackError) {
    throw new Error(callbackError);
  }

  const code = new URL(result.url).searchParams.get('code');
  if (!code) {
    throw new Error('The auth provider did not return a session code.');
  }

  const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);
  if (exchangeError) {
    throw exchangeError;
  }
}

export function signInWithApple(): Promise<void> {
  return signInWithProvider('apple');
}

export function signInWithGoogle(): Promise<void> {
  return signInWithProvider('google');
}
