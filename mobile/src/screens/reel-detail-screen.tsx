import { Image, ScrollView, Text, View } from 'react-native';

import type { Capture } from '@/captures';
import { BackIcon, ExternalIcon, MoreIcon } from '@/components/icons';
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
  const previewWidth = Math.min(width * 0.74, 318);

  return (
    <ScrollView
      contentContainerStyle={styles.detailContent}
      showsVerticalScrollIndicator={false}
      bounces
    >
      <View style={styles.detailNav}>
        <IconButton accessibilityLabel="Back to saved Reels" onPress={onBack}>
          <BackIcon />
        </IconButton>
        <Text numberOfLines={1} style={styles.detailNavTitle}>
          {capture.creator}
        </Text>
        <IconButton accessibilityLabel="Open Reel actions" onPress={onOpenMenu}>
          <MoreIcon />
        </IconButton>
      </View>

      <View style={styles.detailHero}>
        <View style={styles.previewPaper}>
          <View style={[styles.reelPreview, { width: previewWidth }]}>
            <Image source={{ uri: capture.thumbnailUrl }} style={styles.reelPreviewImage} />
          </View>
        </View>

        <View style={styles.sourceBlock}>
          <Text style={styles.sourceCreator}>{capture.creator}</Text>
          {capture.sourceContextSnippet ? (
            <SourceQuote quote={capture.sourceContextSnippet} attribution={`Saved from ${capture.creator}`} />
          ) : (
            <Text style={styles.sourceSnippet}>Source saved. Mentioned will keep the Reel with any books it finds.</Text>
          )}
          <View style={styles.detailSourceAction}>
            <SecondaryButton label="Open source" onPress={onOpenSource} compact />
            <ExternalIcon />
          </View>
        </View>
      </View>

      {actionError ? <InlineMessage tone="error" message={actionError} /> : null}

      {capture.status === 'processing' ? <ProcessingBooks /> : null}
      {capture.status === 'ready' ? <BooksMentioned books={capture.books} /> : null}
      {capture.status === 'no_books' ? <NoBooks onOpenSource={onOpenSource} /> : null}
      {capture.status === 'failed' ? (
        <FailedState isRetrying={isRetrying} onOpenSource={onOpenSource} onRetry={onRetry} />
      ) : null}
    </ScrollView>
  );
}
