import { ScrollView, Text, View } from 'react-native';

import type { Capture } from '@/captures';
import { EmptyCaptures } from '@/components/empty-state';
import { PlusIcon, UserIcon } from '@/components/icons';
import { FadeInView } from '@/components/motion';
import { ReelTile } from '@/components/reel-tile';
import { IconButton, InlineMessage, PrimaryButton, SecondaryButton } from '@/components/ui';
import { styles } from './home-screen.styles';

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
        <Text style={styles.screenSubtitle}>
          Posts you save so Mentioned can find the books, places, and products inside.
        </Text>
      </View>

      {pendingSharedSourceUrl ? (
        <View style={styles.pendingSourcePrompt}>
          <View style={styles.pendingSourceCopy}>
            <Text style={styles.pendingSourceTitle}>Ready to extract</Text>
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
        <InlineMessage message={error} actionLabel={errorActionLabel} onAction={onErrorAction} />
      ) : null}

      {isLoading && captures.length === 0 ? <LoadingState tileWidth={tileWidth} /> : null}
      {!isLoading && captures.length === 0 ? <EmptyCaptures onOpenPaste={onOpenPaste} /> : null}

      {captures.length > 0 ? (
        <View style={styles.grid}>
          {captures.map((capture, index) => (
            <FadeInView key={capture.id} delay={Math.min(index * 40, 240)}>
              <ReelTile
                capture={capture}
                width={tileWidth}
                onPress={() => onOpenCapture(capture)}
              />
            </FadeInView>
          ))}
        </View>
      ) : null}
    </ScrollView>
  );
}

function LoadingState({ tileWidth }: { tileWidth: number }) {
  return (
    <View style={styles.loadingSources}>
      <Text style={styles.loadingSourcesTitle}>Loading saved posts</Text>
      <Text style={styles.loadingSourcesBody}>
        Your saved posts will appear here when they are ready.
      </Text>
      <View style={styles.grid}>
        <View style={[styles.reelSkeletonTile, { width: tileWidth }]} />
        <View style={[styles.reelSkeletonTile, { width: tileWidth }]} />
        <View style={[styles.reelSkeletonTile, { width: tileWidth }]} />
      </View>
    </View>
  );
}
