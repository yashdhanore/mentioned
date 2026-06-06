import { ScrollView, Text, View } from 'react-native';

import type { Capture } from '@/captures';
import { PlusIcon, UserIcon } from '@/components/icons';
import { FadeInView } from '@/components/motion';
import { SourceToBooksPreview } from '@/components/product-preview';
import { ReelTile } from '@/components/reel-tile';
import { IconButton, InlineMessage, PrimaryButton, SecondaryButton } from '@/components/ui';
import { styles } from '@/styles';
import { spacing } from '@/theme';

export function HomeScreen({
  captures,
  error,
  errorActionLabel,
  onErrorAction,
  pendingSharedSourceUrl,
  isSubmittingPendingSharedSource,
  onSavePendingSharedSource,
  onDiscardPendingSharedSource,
  isLoading,
  tileWidth,
  onOpenPaste,
  onOpenProfile,
  onOpenCapture,
}: {
  captures: Capture[];
  error: string | null;
  errorActionLabel?: string;
  onErrorAction?: () => void;
  pendingSharedSourceUrl: string | null;
  isSubmittingPendingSharedSource: boolean;
  onSavePendingSharedSource: () => void;
  onDiscardPendingSharedSource: () => void;
  isLoading: boolean;
  tileWidth: number;
  onOpenPaste: () => void;
  onOpenProfile: () => void;
  onOpenCapture: (capture: Capture) => void;
}) {
  return (
    <ScrollView
      contentContainerStyle={styles.homeContent}
      showsVerticalScrollIndicator={false}
      bounces
    >
      <View style={styles.topNav}>
        <Text style={styles.navBrand}>Mentioned</Text>
        <View style={styles.navActions}>
          <IconButton accessibilityLabel="Paste link" onPress={onOpenPaste}>
            <PlusIcon />
          </IconButton>
          <IconButton accessibilityLabel="Open profile and settings" onPress={onOpenProfile}>
            <UserIcon />
          </IconButton>
        </View>
      </View>

      <View style={styles.homeHeader}>
        <Text style={styles.screenTitle}>Saved posts</Text>
        <Text style={styles.screenSubtitle}>Posts you save so Mentioned can find the books inside.</Text>
      </View>

      {pendingSharedSourceUrl ? (
        <View style={styles.pendingSourcePrompt}>
          <View style={styles.pendingSourceCopy}>
            <Text style={styles.pendingSourceTitle}>Ready to find books</Text>
            <Text ellipsizeMode="middle" numberOfLines={1} style={styles.pendingSourceUrl}>
              {pendingSharedSourceUrl}
            </Text>
          </View>
          <View style={styles.pendingSourceActions}>
            <PrimaryButton
              label={isSubmittingPendingSharedSource ? 'Saving...' : 'Save post'}
              onPress={onSavePendingSharedSource}
              compact
              disabled={isSubmittingPendingSharedSource}
            />
            <SecondaryButton
              label="Discard"
              onPress={onDiscardPendingSharedSource}
              compact
              disabled={isSubmittingPendingSharedSource}
            />
          </View>
        </View>
      ) : null}

      {error ? (
        <InlineMessage
          tone="error"
          message={error}
          actionLabel={errorActionLabel}
          onAction={onErrorAction}
        />
      ) : null}

      {isLoading && captures.length === 0 ? <LoadingState tileWidth={tileWidth} /> : null}
      {!isLoading && captures.length === 0 ? <EmptyCaptures onOpenPaste={onOpenPaste} /> : null}

      {captures.length > 0 ? (
        <View style={styles.grid}>
          {captures.map((capture, index) => {
            const isFeatured = index === 0;
            return (
              <FadeInView key={capture.id} delay={Math.min(index * 40, 240)}>
                <ReelTile
                  capture={capture}
                  featured={isFeatured}
                  width={isFeatured ? tileWidth * 2 + spacing.md : tileWidth}
                  onPress={() => onOpenCapture(capture)}
                />
              </FadeInView>
            );
          })}
        </View>
      ) : null}
    </ScrollView>
  );
}

function LoadingState({ tileWidth }: { tileWidth: number }) {
  return (
    <View style={styles.loadingSources}>
      <Text style={styles.loadingSourcesTitle}>Loading saved posts</Text>
      <Text style={styles.loadingSourcesBody}>Your saved posts will appear here when they are ready.</Text>
      <View style={styles.grid}>
        <View style={[styles.reelSkeletonTile, styles.reelSkeletonTileFeatured, { width: tileWidth * 2 + spacing.md }]} />
        <View style={[styles.reelSkeletonTile, { width: tileWidth }]} />
        <View style={[styles.reelSkeletonTile, { width: tileWidth }]} />
      </View>
    </View>
  );
}

function EmptyCaptures({ onOpenPaste }: { onOpenPaste: () => void }) {
  return (
    <View style={styles.stateCard}>
      <Text style={styles.stateTitle}>No saved posts yet</Text>
      <Text style={styles.stateBody}>Share a post to save it here and start finding books mentioned inside.</Text>
      <View style={styles.emptyPreviewWrap}>
        <SourceToBooksPreview />
      </View>
      <View style={styles.stateActions}>
        <PrimaryButton label="Paste link" onPress={onOpenPaste} compact />
      </View>
    </View>
  );
}
