export type SharedSourcePayload = { url?: string; text?: string };
export type MentionedShareDeepLinkParseResult =
  | { type: 'valid'; sourceUrl: string }
  | { type: 'invalid-share-link' }
  | { type: 'non-share-link' };

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

function supportedNormalizedUrlFromQueryValue(value: string): string | null {
  let currentValue = value;

  for (let attempt = 0; attempt < 3; attempt += 1) {
    const normalizedUrl = supportedNormalizedUrl(currentValue);
    if (normalizedUrl) {
      return normalizedUrl;
    }

    try {
      const decodedValue = decodeURIComponent(currentValue);
      if (decodedValue === currentValue) {
        return null;
      }
      currentValue = decodedValue;
    } catch {
      return null;
    }
  }

  return null;
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
  const result = parseMentionedShareDeepLink(rawUrl);
  return result.type === 'valid' ? result.sourceUrl : null;
}

export function parseMentionedShareDeepLink(rawUrl: string): MentionedShareDeepLinkParseResult {
  return parseMentionedShareDeepLinkWithDepth(rawUrl, 0);
}

function parseMentionedShareDeepLinkWithDepth(rawUrl: string, depth: number): MentionedShareDeepLinkParseResult {
  try {
    const deepLink = new URL(rawUrl);
    const wrappedUrl = wrappedShareDeepLink(deepLink);
    if (wrappedUrl && depth < 2) {
      const wrappedResult = parseMentionedShareDeepLinkWithDepth(wrappedUrl, depth + 1);
      if (wrappedResult.type !== 'non-share-link') {
        return wrappedResult;
      }
    }

    if (deepLink.protocol !== 'mentioned:' || mentionedRoute(deepLink) !== 'share') {
      return { type: 'non-share-link' };
    }

    const sharedUrl = deepLink.searchParams.get('url');
    const sourceUrl = sharedUrl ? supportedNormalizedUrlFromQueryValue(sharedUrl) : null;
    return sourceUrl ? { type: 'valid', sourceUrl } : { type: 'invalid-share-link' };
  } catch {
    return { type: 'non-share-link' };
  }
}

function wrappedShareDeepLink(deepLink: URL): string | null {
  if (mentionedRoute(deepLink) !== 'expo-development-client') {
    return null;
  }

  return deepLink.searchParams.get('url');
}

function mentionedRoute(deepLink: URL): string {
  if (deepLink.hostname) {
    return deepLink.pathname === '' || deepLink.pathname === '/' ? deepLink.hostname : '';
  }

  const pathParts = deepLink.pathname.replace(/^\/+/, '').split('/');
  return pathParts.length === 1 ? pathParts[0] : '';
}
