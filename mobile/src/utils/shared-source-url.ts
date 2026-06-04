export type SharedSourcePayload = { url?: string; text?: string };

const SUPPORTED_HOSTS = new Set(['instagram.com', 'www.instagram.com']);
const URL_PATTERN = /https?:\/\/[^\s<>"']+/g;
const TRAILING_PUNCTUATION_PATTERN = /[\])}.;,!?]+$/g;

function trimUrlCandidate(value: string): string {
  return value.trim().replace(TRAILING_PUNCTUATION_PATTERN, '');
}

function hasSupportedPath(pathname: string): boolean {
  return pathname.includes('/reel/') || pathname.includes('/p/');
}

function supportedUrl(value: string): URL | null {
  try {
    const url = new URL(trimUrlCandidate(value));

    if (url.protocol !== 'https:') {
      return null;
    }

    if (!SUPPORTED_HOSTS.has(url.hostname)) {
      return null;
    }

    if (!hasSupportedPath(url.pathname)) {
      return null;
    }

    return url;
  } catch {
    return null;
  }
}

function normalizeSharedSourceUrl(url: URL): string {
  const normalizedUrl = new URL(url.toString());
  normalizedUrl.hash = '';

  for (const key of Array.from(normalizedUrl.searchParams.keys())) {
    const normalizedKey = key.toLowerCase();
    if (normalizedKey === 'igsh' || normalizedKey.startsWith('utm_')) {
      normalizedUrl.searchParams.delete(key);
    }
  }

  return normalizedUrl.toString();
}

function supportedNormalizedUrl(value: string): string | null {
  const url = supportedUrl(value);
  return url ? normalizeSharedSourceUrl(url) : null;
}

export function isSupportedSharedSourceUrl(value: string): boolean {
  return supportedUrl(value) !== null;
}

export function extractSharedSourceUrl(payload: SharedSourcePayload): string | null {
  if (payload.url) {
    const url = supportedNormalizedUrl(payload.url);
    if (url) {
      return url;
    }
  }

  for (const match of payload.text?.matchAll(URL_PATTERN) ?? []) {
    const url = supportedNormalizedUrl(match[0]);
    if (url) {
      return url;
    }
  }

  return null;
}

export function sharedUrlFromMentionedDeepLink(rawUrl: string): string | null {
  try {
    const deepLink = new URL(rawUrl);

    if (deepLink.protocol !== 'mentioned:' || mentionedRoute(deepLink) !== 'share') {
      return null;
    }

    const sharedUrl = deepLink.searchParams.get('url');
    return sharedUrl ? supportedNormalizedUrl(sharedUrl) : null;
  } catch {
    return null;
  }
}

function mentionedRoute(deepLink: URL): string {
  if (deepLink.hostname) {
    return deepLink.pathname === '' ? deepLink.hostname : '';
  }

  const pathParts = deepLink.pathname.replace(/^\/+/, '').split('/');
  return pathParts.length === 1 ? pathParts[0] : '';
}
