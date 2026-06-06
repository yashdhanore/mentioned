import { Image, Pressable, ScrollView, Text, View } from 'react-native';

import type { BookMention, Capture } from '@/captures';
import { BackIcon, ExternalLinkIcon, MoreIcon } from '@/components/icons';
import {
  BooksMentioned,
  FailedState,
  NoBooks,
  ProcessingBooks,
} from '@/components/books';
import { IconButton, InlineMessage, SecondaryButton, SourceQuote } from '@/components/ui';
import { styles } from '@/styles';

export function ReelDetailScreen({
  capture,
  width,
  actionError,
  isRetrying,
  removingBookId,
  onBack,
  onOpenMenu,
  onOpenRemoveBook,
  onOpenSource,
  onRetry,
}: {
  capture: Capture;
  width: number;
  actionError: string | null;
  isRetrying: boolean;
  removingBookId: string | null;
  onBack: () => void;
  onOpenMenu: () => void;
  onOpenRemoveBook: (book: BookMention) => void;
  onOpenSource: () => void;
  onRetry: () => void;
}) {
  const sourcePreviewWidth = Math.min(Math.max(width * 0.32, 96), 124);
  const sourceHeroWidth = Math.min(Math.max(width * 0.58, 210), 260);
  const inlineError = actionError ? <InlineMessage tone="error" message={actionError} /> : null;

  return (
    <ScrollView
      contentContainerStyle={styles.detailContent}
      showsVerticalScrollIndicator={false}
      bounces
    >
      <View style={styles.detailNav}>
        <IconButton accessibilityLabel="Back to saved items" onPress={onBack}>
          <BackIcon />
        </IconButton>
        <SourceNavIdentity capture={capture} />
        <IconButton accessibilityLabel="Open Reel actions" onPress={onOpenMenu}>
          <MoreIcon />
        </IconButton>
      </View>

      {capture.status === 'ready' ? (
        <>
          <SourceHero
            capture={capture}
            previewWidth={sourceHeroWidth}
            onOpenSource={onOpenSource}
          />
          {inlineError}
          <BooksMentioned
            books={capture.books}
            removingBookId={removingBookId}
            onOpenRemoveBook={onOpenRemoveBook}
          />
        </>
      ) : null}
      {capture.status === 'processing' ? (
        <>
          {inlineError}
          <ProcessingBooks />
          <OriginalSourceSection
            capture={capture}
            previewWidth={sourcePreviewWidth}
            onOpenSource={onOpenSource}
          />
        </>
      ) : null}
      {capture.status === 'no_books' ? (
        <>
          {inlineError}
          <NoBooks onOpenSource={onOpenSource} />
          <OriginalSourceSection
            capture={capture}
            previewWidth={sourcePreviewWidth}
            onOpenSource={onOpenSource}
          />
        </>
      ) : null}
      {capture.status === 'failed' ? (
        <>
          {inlineError}
          <FailedState isRetrying={isRetrying} onOpenSource={onOpenSource} onRetry={onRetry} />
          <OriginalSourceSection
            capture={capture}
            previewWidth={sourcePreviewWidth}
            onOpenSource={onOpenSource}
          />
        </>
      ) : null}
    </ScrollView>
  );
}

function SourceNavIdentity({ capture }: { capture: Capture }) {
  const label = sourceIdentityLabel(capture);

  return (
    <View style={styles.detailNavIdentity}>
      {capture.creatorHandle ? (
        <Image
          source={{ uri: capture.thumbnailUrl }}
          resizeMode="cover"
          style={styles.detailNavAvatar}
        />
      ) : null}
      <Text
        numberOfLines={1}
        style={capture.creatorHandle ? styles.detailNavHandle : styles.detailNavTitle}
      >
        {label}
      </Text>
    </View>
  );
}

function SourceHero({
  capture,
  previewWidth,
  onOpenSource,
}: {
  capture: Capture;
  previewWidth: number;
  onOpenSource: () => void;
}) {
  const savedLabel = savedAtLabel(capture.createdAt);

  return (
    <View style={styles.sourceHero}>
      <View style={styles.sourceHeroStage}>
        <View style={styles.sourceHeroPaper} />
        <View style={[styles.sourceHeroCard, { width: previewWidth }]}>
          <Image
            source={{ uri: capture.thumbnailUrl }}
            resizeMode="cover"
            style={styles.sourceHeroImage}
          />
        </View>
      </View>

      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Open original source"
        style={({ pressed }) => [styles.sourceHeroAction, pressed && styles.pressed]}
        onPress={onOpenSource}
      >
        <Text style={styles.sourceHeroActionText}>Open source</Text>
        <ExternalLinkIcon color="#0E6F68" style={styles.sourceHeroActionIcon} />
      </Pressable>

      <View style={styles.sourceHeroMeta}>
        <View style={styles.sourceHeroIdentity}>
          <Text numberOfLines={1} style={styles.sourceHeroCreator}>
            {sourceIdentityLabel(capture)}
          </Text>
          {savedLabel ? (
            <Text numberOfLines={1} style={styles.sourceHeroSavedAt}>
              {savedLabel}
            </Text>
          ) : null}
        </View>
        {capture.sourceContextSnippet ? (
          <SourceQuote quote={capture.sourceContextSnippet} attribution="From source" />
        ) : null}
      </View>
    </View>
  );
}

function savedAtLabel(createdAt: string): string | null {
  const timestamp = Date.parse(createdAt);
  if (!Number.isFinite(timestamp)) {
    return null;
  }

  const diffMs = Math.max(0, Date.now() - timestamp);
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;

  if (diffMs < minute) {
    return 'Saved just now';
  }
  if (diffMs < hour) {
    return `Saved ${Math.floor(diffMs / minute)}m ago`;
  }
  if (diffMs < day) {
    return `Saved ${Math.floor(diffMs / hour)}h ago`;
  }
  if (diffMs < 7 * day) {
    return `Saved ${Math.floor(diffMs / day)}d ago`;
  }

  return `Saved ${new Date(timestamp).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
  })}`;
}

function sourceIdentityLabel(capture: Capture): string {
  return capture.creatorHandle ? `@${capture.creatorHandle}` : capture.creator;
}

function OriginalSourceSection({
  capture,
  previewWidth,
  onOpenSource,
}: {
  capture: Capture;
  previewWidth: number;
  onOpenSource: () => void;
}) {
  return (
    <View style={styles.originalSourceSection}>
      <Text style={styles.originalSourceTitle}>Original source</Text>
      <View style={styles.originalSourceModule}>
        <View style={[styles.originalSourcePreview, { width: previewWidth }]}>
          <Image source={{ uri: capture.thumbnailUrl }} style={styles.reelPreviewImage} />
        </View>
        <View style={styles.originalSourceCopy}>
          <Text numberOfLines={1} style={styles.sourceCreator}>
            {sourceIdentityLabel(capture)}
          </Text>
          {capture.sourceContextSnippet ? (
            <SourceQuote quote={capture.sourceContextSnippet} attribution="From Instagram" />
          ) : null}
          <View style={styles.detailSourceAction}>
            <SecondaryButton label="Open on Instagram" onPress={onOpenSource} compact />
          </View>
        </View>
      </View>
    </View>
  );
}
