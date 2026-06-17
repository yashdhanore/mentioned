import AsyncStorage from '@react-native-async-storage/async-storage';
import { createClient, processLock, type Provider } from '@supabase/supabase-js';
import { AppState, Platform } from 'react-native';
import 'react-native-url-polyfill/auto';

import { validateSupabaseMobileConfig } from '@/supabase-runtime-config';

export type AuthProvider = Extract<Provider, 'google' | 'apple'>;

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

// Thrown when the user dismisses the provider sign-in flow. Callers treat this
// as a silent no-op rather than surfacing an error banner.
export class AuthCanceledError extends Error {
  constructor() {
    super('Sign in was canceled.');
    this.name = 'AuthCanceledError';
  }
}

export function assertSupabaseConfigured(): void {
  if (!isSupabaseConfigured) {
    throw new Error('Supabase auth is not configured for this build.');
  }
}

export async function currentAccessToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}
