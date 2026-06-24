import type { SavedSourceResponse, SavedSourceStatus, SourceItemInSavedSource } from './api';

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
  skipReason: string | null;
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

function thumbnailForSavedSource(savedSource: Pick<SavedSourceResponse, 'thumbnail_url'>) {
  return compact(savedSource.thumbnail_url);
}

function visibleBookItems(items: SourceItemInSavedSource[]): BookMention[] {
  return items
    .filter((item) => item.category === 'book')
    .filter((item) => item.confidence === null || item.confidence >= MIN_VISIBLE_CONFIDENCE)
    .filter((item) => compact(item.title))
    .sort((left, right) => left.position - right.position)
    .map((item) => ({
      id: item.id,
      title: item.title.trim(),
      author: compact(item.author),
      synopsis: null,
      coverImageUrl: compact(item.cover_image_url),
      initials: initialsFor(item.title),
      color: colorFor(item.id),
    }));
}

function statusFor(savedSourceStatus: SavedSourceStatus, books: BookMention[]): CaptureStatus {
  if (savedSourceStatus === 'processing') {
    return 'processing';
  }
  if (savedSourceStatus === 'done') {
    return books.length > 0 ? 'ready' : 'no_books';
  }
  return 'failed';
}

export function buildCapturesFromSavedSources(savedSources: SavedSourceResponse[]): Capture[] {
  return savedSources.map(captureFromSavedSource);
}

export function captureFromSavedSourceCreated(savedSource: SavedSourceResponse): Capture {
  return captureFromSavedSource(savedSource);
}

export function captureFromSavedSource(savedSource: SavedSourceResponse): Capture {
  const books = visibleBookItems(savedSource.items);
  return {
    id: savedSource.id,
    creator: 'Instagram',
    creatorHandle: compact(savedSource.source_creator_handle),
    status: statusFor(savedSource.status, books),
    thumbnailUrl: thumbnailForSavedSource(savedSource),
    sourceUrl: savedSource.source_url,
    createdAt: savedSource.created_at,
    sourceContextSnippet: null,
    books,
    errorMessage: savedSource.error_message,
    skipReason: compact(savedSource.skip_reason),
  };
}

export function mergeSavedSourcesWithCaptures(
  savedSources: SavedSourceResponse[],
  existingCaptures: Capture[],
): Capture[] {
  const existingById = new Map(existingCaptures.map((capture) => [capture.id, capture]));

  return savedSources.map((savedSource) => {
    const savedSourceCapture = captureFromSavedSource(savedSource);
    const existingCapture = existingById.get(savedSource.id);
    if (!existingCapture) {
      return savedSourceCapture;
    }

    return {
      ...savedSourceCapture,
      sourceContextSnippet: existingCapture.sourceContextSnippet,
    };
  });
}
