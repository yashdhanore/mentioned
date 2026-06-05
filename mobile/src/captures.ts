import type { JobResponse, JobStatus, MentionInJob } from './api';

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
  status: CaptureStatus;
  thumbnailUrl: string;
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

function placeholderThumbnail(jobId: string) {
  const seed = jobId.replace(/[^a-z0-9]/gi, '').slice(0, 24) || 'mentioned';
  return `https://picsum.photos/seed/mentioned-${seed}/900/1600`;
}

function thumbnailForJob(job: JobResponse) {
  return compact(job.thumbnail_url) ?? placeholderThumbnail(job.job_id);
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

export function buildCaptures(jobs: JobResponse[]): Capture[] {
  return jobs.map(captureFromJobDetail);
}

export function captureFromJobCreated(jobId: string, sourceUrl: string): Capture {
  return {
    id: jobId,
    creator: 'Instagram',
    status: 'processing',
    thumbnailUrl: placeholderThumbnail(jobId),
    sourceUrl,
    createdAt: new Date().toISOString(),
    sourceContextSnippet: null,
    books: [],
    errorMessage: null,
  };
}

export function captureFromJobDetail(job: JobResponse): Capture {
  const books = visibleBookMentions(job.mentions);
  return {
    id: job.job_id,
    creator: 'Instagram',
    status: statusFor(job.status, books),
    thumbnailUrl: thumbnailForJob(job),
    sourceUrl: job.source_url,
    createdAt: job.created_at,
    sourceContextSnippet: null,
    books,
    errorMessage: job.error_message,
  };
}
