import type { JobListItem, JobResponse, JobStatus, MentionInJob } from './api';

export type CaptureStatus = 'ready' | 'processing' | 'no_books' | 'failed';

export type BookMention = {
  id: string;
  title: string;
  author: string | null;
  synopsis: string | null;
  coverImageUrl: string | null;
  initials: string;
  color: string;
};

export type Capture = {
  id: string;
  creator: string;
  creatorHandle: string | null;
  status: CaptureStatus;
  thumbnailUrl: string | null;
  sourceUrl: string;
  createdAt: string;
  sourceContextSnippet: string | null;
  books: BookMention[];
  errorMessage: string | null;
};

const MIN_VISIBLE_CONFIDENCE = 0.6;
const BOOK_COLORS = ['#345D8C', '#0E6F68', '#53615B', '#8A5E00', '#4B6378'];

function compact(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}

function initialsFor(title: string) {
  const words = title
    .split(/\s+/)
    .map((word) => word.replace(/[^a-z0-9]/gi, ''))
    .filter(Boolean);

  if (words.length >= 2) {
    return `${words[0][0]}${words[1][0]}`.toUpperCase();
  }

  return (words[0] || title).slice(0, 2).toUpperCase();
}

function colorFor(id: string) {
  let hash = 0;
  for (let index = 0; index < id.length; index += 1) {
    hash = (hash + id.charCodeAt(index)) % BOOK_COLORS.length;
  }
  return BOOK_COLORS[hash];
}

function thumbnailForJob(job: Pick<JobResponse, 'thumbnail_url'>) {
  return compact(job.thumbnail_url);
}

function visibleBookMentions(mentions: MentionInJob[]): BookMention[] {
  return mentions
    .filter((mention) => mention.category === 'book')
    .filter((mention) => mention.confidence === null || mention.confidence >= MIN_VISIBLE_CONFIDENCE)
    .filter((mention) => compact(mention.title))
    .map((mention) => ({
      id: mention.id,
      title: mention.title.trim(),
      author: compact(mention.author),
      synopsis: null,
      coverImageUrl: compact(mention.cover_image_url),
      initials: initialsFor(mention.title),
      color: colorFor(mention.id),
    }));
}

function statusFor(jobStatus: JobStatus, books: BookMention[]): CaptureStatus {
  if (jobStatus === 'pending') {
    return 'processing';
  }
  if (jobStatus === 'done') {
    return books.length > 0 ? 'ready' : 'no_books';
  }
  return 'failed';
}

function listStatusFor(jobStatus: JobStatus): CaptureStatus {
  if (jobStatus === 'pending') {
    return 'processing';
  }
  if (jobStatus === 'done') {
    return 'ready';
  }
  return 'failed';
}

export function buildCaptures(jobs: JobResponse[]): Capture[] {
  return jobs.map(captureFromJobDetail);
}

export function buildCapturesFromJobList(jobs: JobListItem[]): Capture[] {
  return jobs.map(captureFromJobListItem);
}

export function captureFromJobCreated(jobId: string, sourceUrl: string): Capture {
  return {
    id: jobId,
    creator: 'Instagram',
    creatorHandle: null,
    status: 'processing',
    thumbnailUrl: null,
    sourceUrl,
    createdAt: new Date().toISOString(),
    sourceContextSnippet: null,
    books: [],
    errorMessage: null,
  };
}

export function captureFromJobListItem(job: JobListItem): Capture {
  return {
    id: job.job_id,
    creator: 'Instagram',
    creatorHandle: compact(job.source_creator_handle),
    status: listStatusFor(job.status),
    thumbnailUrl: thumbnailForJob(job),
    sourceUrl: job.source_url,
    createdAt: job.created_at,
    sourceContextSnippet: null,
    books: [],
    errorMessage: null,
  };
}

export function mergeJobListItemsWithCaptures(
  jobs: JobListItem[],
  existingCaptures: Capture[],
): Capture[] {
  const existingById = new Map(existingCaptures.map((capture) => [capture.id, capture]));

  return jobs.map((job) => {
    const listedCapture = captureFromJobListItem(job);
    const existingCapture = existingById.get(job.job_id);
    if (!existingCapture) {
      return listedCapture;
    }

    return {
      ...listedCapture,
      books: existingCapture.books,
      errorMessage: existingCapture.errorMessage,
      sourceContextSnippet: existingCapture.sourceContextSnippet,
      status:
        listedCapture.status === 'ready' && existingCapture.status === 'no_books'
          ? 'no_books'
          : listedCapture.status,
    };
  });
}

export function captureFromJobDetail(job: JobResponse): Capture {
  const books = visibleBookMentions(job.mentions);
  return {
    id: job.job_id,
    creator: 'Instagram',
    creatorHandle: compact(job.source_creator_handle),
    status: statusFor(job.status, books),
    thumbnailUrl: thumbnailForJob(job),
    sourceUrl: job.source_url,
    createdAt: job.created_at,
    sourceContextSnippet: null,
    books,
    errorMessage: job.error_message,
  };
}
