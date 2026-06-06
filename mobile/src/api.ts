const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000';
const DEFAULT_DEV_USER_ID = '00000000-0000-4000-8000-000000000001';
const publicAuthMode = process.env.EXPO_PUBLIC_AUTH_MODE?.trim().toLowerCase() || '';

export const API_BASE_URL = (
  process.env.EXPO_PUBLIC_API_BASE_URL?.trim() || DEFAULT_API_BASE_URL
).replace(/\/+$/, '');

export const PRIVACY_POLICY_URL =
  process.env.EXPO_PUBLIC_PRIVACY_POLICY_URL?.trim().replace(/\/+$/, '') || null;

export const isDevAuthEnabled = publicAuthMode === 'dev';
export const DEV_USER_ID =
  process.env.EXPO_PUBLIC_DEV_USER_ID?.trim() || DEFAULT_DEV_USER_ID;

type AccessTokenProvider = () => Promise<string | null> | string | null;

let accessTokenProvider: AccessTokenProvider | null = null;

export function setAccessTokenProvider(provider: AccessTokenProvider): void {
  accessTokenProvider = provider;
}

export function clearAccessTokenProvider(): void {
  accessTokenProvider = null;
}

export function devAccessToken(): string {
  return `dev:${DEV_USER_ID}`;
}

function isProductionBuild(): boolean {
  return process.env.EXPO_PUBLIC_APP_ENV?.trim().toLowerCase() === 'production';
}

function isLocalHost(hostname: string): boolean {
  return ['localhost', '127.0.0.1', '0.0.0.0', '::1'].includes(hostname);
}

function validateRuntimeConfig(): void {
  if (publicAuthMode && publicAuthMode !== 'dev') {
    throw new Error('EXPO_PUBLIC_AUTH_MODE must be "dev" or unset.');
  }

  if (!isProductionBuild()) {
    return;
  }

  if (isDevAuthEnabled) {
    throw new Error('Production mobile builds must not set EXPO_PUBLIC_AUTH_MODE=dev.');
  }

  if (process.env.EXPO_PUBLIC_DEV_USER_ID?.trim()) {
    throw new Error('Production mobile builds must not define EXPO_PUBLIC_DEV_USER_ID.');
  }

  let parsedUrl: URL;
  try {
    parsedUrl = new URL(API_BASE_URL);
  } catch {
    throw new Error('EXPO_PUBLIC_API_BASE_URL must be a valid URL in production builds.');
  }

  if (parsedUrl.protocol !== 'https:' || isLocalHost(parsedUrl.hostname)) {
    throw new Error('Production mobile builds require a non-local HTTPS API base URL.');
  }

  if (!PRIVACY_POLICY_URL) {
    throw new Error('Production mobile builds require EXPO_PUBLIC_PRIVACY_POLICY_URL.');
  }

  let parsedPrivacyUrl: URL;
  try {
    parsedPrivacyUrl = new URL(PRIVACY_POLICY_URL);
  } catch {
    throw new Error('EXPO_PUBLIC_PRIVACY_POLICY_URL must be a valid URL in production builds.');
  }

  if (parsedPrivacyUrl.protocol !== 'https:' || isLocalHost(parsedPrivacyUrl.hostname)) {
    throw new Error('Production mobile builds require a non-local HTTPS privacy policy URL.');
  }
}

validateRuntimeConfig();

export type JobStatus = 'pending' | 'done' | 'failed';

export type JobResponse = {
  job_id: string;
  source_url: string;
  thumbnail_url: string | null;
  source_creator_handle: string | null;
  status: JobStatus;
  error_message: string | null;
  created_at: string;
  finished_at: string | null;
  mentions: MentionInJob[];
};

export type MentionInJob = {
  id: string;
  book_id: string | null;
  title: string;
  author: string | null;
  category: string;
  confidence: number | null;
  google_books_url: string | null;
  cover_image_url: string | null;
};

export type JobListItem = {
  job_id: string;
  status: JobStatus;
  source_url: string;
  thumbnail_url: string | null;
  source_creator_handle: string | null;
  created_at: string;
};

export type PushPlatform = 'ios' | 'android';

export type DeleteMentionResponse = {
  id: string;
  deleted: boolean;
};

type ApiErrorPayload = {
  error_code?: string;
  message?: string;
  detail?: string | { error_code?: string; message?: string };
};

export class ApiError extends Error {
  status: number;
  errorCode: string | null;

  constructor(status: number, message: string, errorCode: string | null = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.errorCode = errorCode;
  }
}

async function authHeaders(): Promise<Record<string, string>> {
  const token = accessTokenProvider ? await accessTokenProvider() : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function parseApiError(status: number, payload: ApiErrorPayload | null): ApiError {
  if (!payload) {
    return new ApiError(status, 'The request failed.');
  }
  // New backend format: {error_code, message}
  if (payload.error_code || payload.message) {
    return new ApiError(status, payload.message || 'The request failed.', payload.error_code || null);
  }
  // Legacy format: {detail: string | {error_code, message}}
  const detail = payload.detail;
  if (typeof detail === 'string') {
    return new ApiError(status, detail);
  }
  if (detail && typeof detail === 'object') {
    return new ApiError(status, detail.message || 'The request failed.', detail.error_code || null);
  }
  return new ApiError(status, 'The request failed.');
}

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = init.headers as Record<string, string> | undefined;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(await authHeaders()),
      ...headers,
    },
  });

  const rawBody = await response.text();
  const payload = rawBody ? JSON.parse(rawBody) : null;

  if (!response.ok) {
    throw parseApiError(response.status, payload as ApiErrorPayload | null);
  }

  return payload as T;
}

export function errorMessage(error: unknown, fallback = 'Something went wrong. Please try again.') {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

// --- Jobs ---

export async function createJob(url: string): Promise<{ job_id: string; status: JobStatus }> {
  return requestJson<{ job_id: string; status: JobStatus }>('/v1/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
}

export async function listJobs(): Promise<JobListItem[]> {
  return requestJson<JobListItem[]>('/v1/jobs');
}

export async function listAllJobs(): Promise<JobListItem[]> {
  return listJobs();
}

export async function getJob(jobId: string): Promise<JobResponse> {
  return requestJson<JobResponse>(`/v1/jobs/${jobId}`);
}

// --- Mentions ---

export async function deleteMention(mentionId: string): Promise<DeleteMentionResponse> {
  return requestJson<DeleteMentionResponse>(`/v1/mentions/${mentionId}`, {
    method: 'DELETE',
  });
}

// --- Push notifications ---

export async function registerPushToken(
  expoPushToken: string,
  platform: PushPlatform,
): Promise<{ registered: boolean }> {
  return requestJson<{ registered: boolean }>('/v1/push-tokens', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ expo_push_token: expoPushToken, platform }),
  });
}

export async function disablePushToken(expoPushToken: string): Promise<{ disabled: boolean }> {
  return requestJson<{ disabled: boolean }>('/v1/push-tokens/disable', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ expo_push_token: expoPushToken }),
  });
}
