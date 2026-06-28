import type { SavedSourceResponse, SavedSourceStatus, SourceItemInSavedSource } from './api';

export type CaptureStatus = 'ready' | 'processing' | 'no_mentions' | 'failed';

export type MentionCategory = 'book' | 'place' | 'product';

export type Mention = {
  id: string;
  category: MentionCategory;
  title: string;
  subtitle: string | null;
  coverImageUrl: string | null;
  formattedAddress: string | null;
  latitude: number | null;
  longitude: number | null;
  mapsUrl: string | null;
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
  mentions: Mention[];
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

const MENTION_CATEGORIES: readonly MentionCategory[] = ['book', 'place', 'product'];

function asMentionCategory(value: string): MentionCategory | null {
  return (MENTION_CATEGORIES as readonly string[]).includes(value)
    ? (value as MentionCategory)
    : null;
}

function visibleMentions(items: SourceItemInSavedSource[]): Mention[] {
  return items
    // MIN_VISIBLE_CONFIDENCE is shared across all types for now; revisit per
    // type once we have real place/product extraction quality data.
    .filter((item) => item.confidence === null || item.confidence >= MIN_VISIBLE_CONFIDENCE)
    .filter((item) => compact(item.title))
    .map((item) => ({ item, category: asMentionCategory(item.category) }))
    .filter((entry): entry is { item: SourceItemInSavedSource; category: MentionCategory } =>
      entry.category !== null,
    )
    .sort((left, right) => left.item.position - right.item.position)
    .map(({ item, category }) => ({
      id: item.id,
      category,
      title: item.title.trim(),
      // Places surface their resolved address here; books use the author.
      subtitle: category === 'place' ? compact(item.formatted_address) : compact(item.author),
      coverImageUrl: compact(item.cover_image_url),
      formattedAddress: compact(item.formatted_address),
      latitude: item.latitude,
      longitude: item.longitude,
      mapsUrl: compact(item.maps_url),
      initials: initialsFor(item.title),
      color: colorFor(item.id),
    }));
}

export function mapsUrlForMention(mention: Mention): string | null {
  if (mention.category !== 'place') {
    return null;
  }
  if (mention.mapsUrl) {
    return mention.mapsUrl;
  }
  if (mention.latitude !== null && mention.longitude !== null) {
    return `https://www.google.com/maps/search/?api=1&query=${mention.latitude},${mention.longitude}`;
  }
  return null;
}

function statusFor(savedSourceStatus: SavedSourceStatus, mentions: Mention[]): CaptureStatus {
  if (savedSourceStatus === 'processing') {
    return 'processing';
  }
  if (savedSourceStatus === 'done') {
    return mentions.length > 0 ? 'ready' : 'no_mentions';
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
  const mentions = visibleMentions(savedSource.items);
  return {
    id: savedSource.id,
    creator: 'Instagram',
    creatorHandle: compact(savedSource.source_creator_handle),
    status: statusFor(savedSource.status, mentions),
    thumbnailUrl: thumbnailForSavedSource(savedSource),
    sourceUrl: savedSource.source_url,
    createdAt: savedSource.created_at,
    sourceContextSnippet: null,
    mentions,
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
