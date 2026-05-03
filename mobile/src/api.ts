const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000';
const DEFAULT_DEV_USER_ID = '00000000-0000-4000-8000-000000000001';
const MAX_PAGES = 5;

export const API_BASE_URL = (
  process.env.EXPO_PUBLIC_API_BASE_URL?.trim() || DEFAULT_API_BASE_URL
).replace(/\/+$/, '');

export const DEV_USER_ID = process.env.EXPO_PUBLIC_DEV_USER_ID?.trim() || DEFAULT_DEV_USER_ID;

export type JobStatus =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'partial'
  | 'failed'
  | 'canceled'
  | 'expired';

export type JobResponse = {
  job_id: string;
  source_url: string;
  source_kind: string;
  status: JobStatus;
  current_stage: string | null;
  progress: number;
  attempt_count: number;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  links: {
    self: string;
    result: string;
  };
};

export type JobListResponse = {
  items: JobResponse[];
  next_cursor: string | null;
};

export type SavedMentionResponse = {
  mention_id: string;
  category: string;
  label: string;
  author_or_creator: string | null;
  description: string | null;
  source_job_id: string;
  source_url: string;
  source_platform: string;
  source_creator: string | null;
  source_context_snippet: string | null;
  confidence: number | null;
  created_at: string;
  updated_at: string;
};

export type SavedMentionListResponse = {
  items: SavedMentionResponse[];
  next_cursor: string | null;
};

export type TextResultResponse = {
  caption_text: string | null;
  spoken_text: string | null;
  visual_text: string | null;
  image_text: string | null;
  merged_text: string;
  warnings: string[];
  debug: unknown;
};

export type JobResultResponse = {
  job_id: string;
  source_url: string;
  source_kind: string;
  status: JobStatus;
  current_stage: string | null;
  progress: number;
  text: TextResultResponse;
  stage_runs: unknown[];
  artifacts: unknown[];
};

type ApiErrorPayload = {
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

function authHeaders(): Record<string, string> {
  return {
    Authorization: `Bearer dev:${DEV_USER_ID}`,
  };
}

function pathWithQuery(path: string, params: Record<string, string | number | null | undefined>) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      query.set(key, String(value));
    }
  });
  const queryString = query.toString();
  return queryString ? `${path}?${queryString}` : path;
}

function parseApiError(status: number, payload: ApiErrorPayload | null): ApiError {
  const detail = payload?.detail;
  if (typeof detail === 'string') {
    return new ApiError(status, detail);
  }
  if (detail && typeof detail === 'object') {
    return new ApiError(status, detail.message || 'The request failed.', detail.error_code || null);
  }
  return new ApiError(status, 'The request failed.');
}

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...authHeaders(),
      ...init.headers,
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

export async function createJob(url: string): Promise<JobResponse> {
  return requestJson<JobResponse>('/v1/jobs', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      url,
      idempotency_key: `mobile-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`,
    }),
  });
}

export async function listJobs(cursor?: string): Promise<JobListResponse> {
  return requestJson<JobListResponse>(pathWithQuery('/v1/jobs', { limit: 100, cursor }));
}

export async function listAllJobs(): Promise<JobResponse[]> {
  const jobs: JobResponse[] = [];
  let cursor: string | null = null;

  for (let page = 0; page < MAX_PAGES; page += 1) {
    const payload = await listJobs(cursor || undefined);
    jobs.push(...payload.items);
    cursor = payload.next_cursor;
    if (!cursor) {
      break;
    }
  }

  return jobs;
}

export async function getJob(jobId: string): Promise<JobResponse> {
  return requestJson<JobResponse>(`/v1/jobs/${jobId}`);
}

export async function rerunJob(jobId: string): Promise<JobResponse> {
  return requestJson<JobResponse>(`/v1/jobs/${jobId}/rerun`, { method: 'POST' });
}

export async function listMentions(cursor?: string): Promise<SavedMentionListResponse> {
  return requestJson<SavedMentionListResponse>(pathWithQuery('/v1/mentions', { limit: 100, cursor }));
}

export async function listAllMentions(): Promise<SavedMentionResponse[]> {
  const mentions: SavedMentionResponse[] = [];
  let cursor: string | null = null;

  for (let page = 0; page < MAX_PAGES; page += 1) {
    const payload = await listMentions(cursor || undefined);
    mentions.push(...payload.items);
    cursor = payload.next_cursor;
    if (!cursor) {
      break;
    }
  }

  return mentions;
}

export async function getJobResult(jobId: string): Promise<JobResultResponse> {
  return requestJson<JobResultResponse>(`/v1/jobs/${jobId}/result`);
}
