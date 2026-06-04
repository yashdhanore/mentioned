import { Image, Pressable, ScrollView, Text, View } from 'react-native';

import type { Capture } from '@/captures';
import { BackIcon, MoreIcon } from '@/components/icons';
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
  onBack,
  onOpenMenu,
  onOpenSource,
  onRetry,
}: {
  capture: Capture;
  width: number;
  actionError: string | null;
  isRetrying: boolean;
  onBack: () => void;
  onOpenMenu: () => void;
  onOpenSource: () => void;
  onRetry: () => void;
}) {
  const sourcePreviewWidth = Math.min(Math.max(width * 0.32, 96), 124);
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
        <Text numberOfLines={1} style={styles.detailNavTitle}>
          {capture.creator}
        </Text>
        <IconButton accessibilityLabel="Open Reel actions" onPress={onOpenMenu}>
          <MoreIcon />
        </IconButton>
      </View>

      {capture.status === 'ready' ? (
        <>
          <SourceSummary capture={capture} onOpenSource={onOpenSource} />
          {inlineError}
          <BooksMentioned books={capture.books} />
          <OriginalSourceSection
            capture={capture}
            previewWidth={sourcePreviewWidth}
            onOpenSource={onOpenSource}
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

function SourceSummary({
  capture,
  onOpenSource,
}: {
  capture: Capture;
  onOpenSource: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="Open original source"
      style={({ pressed }) => [styles.sourceSummary, pressed && styles.pressed]}
      onPress={onOpenSource}
    >
      <Image source={{ uri: capture.thumbnailUrl }} style={styles.sourceSummaryImage} />
      <View style={styles.sourceSummaryCopy}>
        <Text numberOfLines={1} style={styles.sourceSummaryLabel}>
          Saved source
        </Text>
        <Text numberOfLines={1} style={styles.sourceSummaryCreator}>
          {capture.creator}
        </Text>
      </View>
      <Text style={styles.sourceSummaryAction}>Open</Text>
    </Pressable>
  );
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
            {capture.creator}
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
