export type SupabaseMobileRuntimeConfig = {
  appEnv?: string;
  supabaseUrl: string;
  supabasePublishableKey: string;
  authRedirectUrlOverride: string;
};

function isProductionBuild(appEnv?: string): boolean {
  return appEnv?.trim().toLowerCase() === 'production';
}

function isLocalHost(hostname: string): boolean {
  return ['localhost', '127.0.0.1', '0.0.0.0', '::1'].includes(hostname);
}

const BASE64_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';

function decodeBase64Ascii(value: string): string | null {
  let buffer = 0;
  let bits = 0;
  let output = '';

  for (const char of value.replace(/=+$/, '')) {
    const index = BASE64_ALPHABET.indexOf(char);
    if (index < 0) {
      return null;
    }
    buffer = (buffer << 6) | index;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      output += String.fromCharCode((buffer >> bits) & 0xff);
    }
  }

  return output;
}

function decodeBase64UrlJson(segment: string): Record<string, unknown> | null {
  try {
    const normalized = segment.replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized.padEnd(normalized.length + ((4 - (normalized.length % 4)) % 4), '=');
    const decoded = decodeBase64Ascii(padded);
    if (!decoded) {
      return null;
    }
    return JSON.parse(decoded) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function isUnsafeSupabasePublicKey(value: string): boolean {
  const key = value.trim();
  if (!key) {
    return false;
  }
  if (key.startsWith('sb_secret_')) {
    return true;
  }
  const jwtPayload = key.split('.')[1];
  const parsedPayload = jwtPayload ? decodeBase64UrlJson(jwtPayload) : null;
  return parsedPayload?.role === 'service_role';
}

export function validateSupabaseMobileConfig(config: SupabaseMobileRuntimeConfig): void {
  if (!isProductionBuild(config.appEnv)) {
    return;
  }
  if (!config.supabaseUrl || !config.supabasePublishableKey) {
    throw new Error('Production mobile builds require EXPO_PUBLIC_SUPABASE_URL and EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY.');
  }
  if (isUnsafeSupabasePublicKey(config.supabasePublishableKey)) {
    throw new Error('Production mobile builds must not expose a Supabase secret or service-role key.');
  }
  if (config.authRedirectUrlOverride.trim()) {
    throw new Error('Production mobile builds must not set EXPO_PUBLIC_AUTH_REDIRECT_URL.');
  }

  let parsedUrl: URL;
  try {
    parsedUrl = new URL(config.supabaseUrl);
  } catch {
    throw new Error('EXPO_PUBLIC_SUPABASE_URL must be a valid URL in production builds.');
  }
  if (parsedUrl.protocol !== 'https:' || isLocalHost(parsedUrl.hostname)) {
    throw new Error('Production mobile builds require a non-local HTTPS Supabase URL.');
  }
}
