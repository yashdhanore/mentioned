import { Image, Pressable, ScrollView, Text, View } from 'react-native';

import type { Capture } from '@/captures';
import {
  BooksMentioned,
  FailedState,
  NoBooks,
  ProcessingBooks,
} from '@/components/books';
import { InlineMessage } from '@/components/ui';
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
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Back to saved Reels"
          style={({ pressed }) => [styles.backButton, pressed && styles.pressed]}
          onPress={onBack}
        >
          <Text style={styles.backText}>Back</Text>
        </Pressable>
        <Text numberOfLines={1} style={styles.detailNavTitle}>
          {capture.creator}
        </Text>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Open Reel actions"
          style={({ pressed }) => [styles.navSquareButton, pressed && styles.pressed]}
          onPress={onOpenMenu}
        >
          <Text style={styles.navButtonText}>...</Text>
        </Pressable>
      </View>

      <View style={styles.previewWrap}>
        <View style={[styles.reelPreview, { width: previewWidth }]}>
          <Image source={{ uri: capture.thumbnailUrl }} style={styles.reelPreviewImage} />
        </View>
      </View>

      <View style={styles.sourceBlock}>
        <Text style={styles.sourceCreator}>{capture.creator}</Text>
        {capture.sourceContextSnippet ? (
          <Text numberOfLines={2} style={styles.sourceSnippet}>
            {capture.sourceContextSnippet}
          </Text>
        ) : null}
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
