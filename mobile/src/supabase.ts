import AsyncStorage from '@react-native-async-storage/async-storage';
import { createClient, processLock, type Provider } from '@supabase/supabase-js';
import * as Linking from 'expo-linking';
import * as WebBrowser from 'expo-web-browser';
import { AppState, Platform } from 'react-native';
import 'react-native-url-polyfill/auto';

import { validateSupabaseMobileConfig } from '@/supabase-runtime-config';

WebBrowser.maybeCompleteAuthSession();

export type AuthProvider = Extract<Provider, 'google'>;

const AUTH_CALLBACK_PATH = 'auth/callback';
const authRedirectUrlOverride = process.env.EXPO_PUBLIC_AUTH_REDIRECT_URL?.trim() || '';
const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL?.trim() || '';
const supabasePublishableKey =
  process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY?.trim() ||
  process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY?.trim() ||
  '';

export const isSupabaseConfigured = Boolean(supabaseUrl && supabasePublishableKey);

validateSupabaseMobileConfig({
  appEnv: process.env.EXPO_PUBLIC_APP_ENV,
  supabaseUrl,
  supabasePublishableKey,
  authRedirectUrlOverride,
});

export const supabase = createClient(
  supabaseUrl || 'http://127.0.0.1',
  supabasePublishableKey || 'missing-publishable-key',
  {
    auth: {
      ...(Platform.OS !== 'web' ? { storage: AsyncStorage } : {}),
      autoRefreshToken: true,
      detectSessionInUrl: false,
      flowType: 'pkce',
      lock: processLock,
      persistSession: true,
    },
  },
);

if (Platform.OS !== 'web') {
  AppState.addEventListener('change', (state) => {
    if (state === 'active') {
      void supabase.auth.startAutoRefresh();
      return;
    }
    void supabase.auth.stopAutoRefresh();
  });
}

function assertSupabaseConfigured(): void {
  if (!isSupabaseConfigured) {
    throw new Error('Supabase auth is not configured for this build.');
  }
}

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

export async function signInWithProvider(provider: AuthProvider): Promise<void> {
  assertSupabaseConfigured();

  const redirectTo = authRedirectUrl();
  if (__DEV__) {
    console.info(`[auth] OAuth redirect URL: ${redirectTo}`);
  }
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
    throw new Error('Sign in was canceled.');
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

export async function currentAccessToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}
