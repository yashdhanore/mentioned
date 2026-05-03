import type { JobResponse, JobResultResponse, SavedMentionResponse } from './api';

export type CaptureStatus = 'ready' | 'processing' | 'no_books' | 'failed';

export type BookMention = {
  id: string;
  title: string;
  author: string | null;
  synopsis: string | null;
  initials: string;
  color: string;
};

export type Capture = {
  id: string;
  creator: string;
  status: CaptureStatus;
  thumbnailUrl: string;
  sourceUrl: string;
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

function snippet(value: string | null | undefined, maxLength = 180): string | null {
  const cleaned = compact(value)?.replace(/\s+/g, ' ');
  if (!cleaned) {
    return null;
  }
  return cleaned.length > maxLength ? `${cleaned.slice(0, maxLength).trimEnd()}...` : cleaned;
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

function visibleBookMentions(mentions: SavedMentionResponse[]): BookMention[] {
  return mentions
    .filter((mention) => mention.category === 'book')
    .filter((mention) => mention.save_state === 'active')
    .filter((mention) => mention.confidence === null || mention.confidence >= MIN_VISIBLE_CONFIDENCE)
    .filter((mention) => compact(mention.display_label))
    .map((mention) => ({
      id: mention.mention_id,
      title: mention.display_label.trim(),
      author: compact(mention.display_author_or_creator),
      synopsis: snippet(mention.display_description) || snippet(mention.evidence_text),
      initials: initialsFor(mention.display_label),
      color: colorFor(mention.mention_id),
    }));
}

function statusFor(job: JobResponse, books: BookMention[]): CaptureStatus {
  if (job.status === 'queued' || job.status === 'running') {
    return 'processing';
  }
  if (job.status === 'succeeded' || job.status === 'partial') {
    return books.length > 0 ? 'ready' : 'no_books';
  }
  return 'failed';
}

function creatorFor(job: JobResponse, mentions: SavedMentionResponse[]) {
  return compact(mentions.find((mention) => compact(mention.source_creator))?.source_creator) || 'Instagram';
}

function sourceContextFor(mentions: SavedMentionResponse[]) {
  return snippet(mentions.find((mention) => compact(mention.source_context_snippet))?.source_context_snippet);
}

export function buildCaptures(jobs: JobResponse[], mentions: SavedMentionResponse[]): Capture[] {
  const mentionsByJob = mentions.reduce<Map<string, SavedMentionResponse[]>>((groups, mention) => {
    const current = groups.get(mention.source_job_id) || [];
    current.push(mention);
    groups.set(mention.source_job_id, current);
    return groups;
  }, new Map());

  return jobs.map((job) => {
    const jobMentions = mentionsByJob.get(job.job_id) || [];
    const books = visibleBookMentions(jobMentions);
    return {
      id: job.job_id,
      creator: creatorFor(job, jobMentions),
      status: statusFor(job, books),
      thumbnailUrl: placeholderThumbnail(job.job_id),
      sourceUrl: job.source_url,
      sourceContextSnippet: sourceContextFor(jobMentions),
      books,
      errorMessage: job.error_message,
    };
  });
}

export function captureFromJob(job: JobResponse): Capture {
  return buildCaptures([job], [])[0];
}

export function applyResultFallback(capture: Capture, result: JobResultResponse): Capture {
  if (capture.sourceContextSnippet) {
    return capture;
  }

  const fallback =
    snippet(result.text.caption_text) ||
    snippet(result.text.visual_text) ||
    snippet(result.text.image_text) ||
    snippet(result.text.merged_text);

  return {
    ...capture,
    sourceContextSnippet: fallback,
  };
}
