import { ScrollView, Text, View } from 'react-native';

import type { Capture } from '@/captures';
import { PlusIcon, UserIcon } from '@/components/icons';
import { FadeInView } from '@/components/motion';
import { SourceToBooksPreview } from '@/components/product-preview';
import { ReelTile } from '@/components/reel-tile';
import { IconButton, InlineMessage, PrimaryButton } from '@/components/ui';
import { styles } from '@/styles';
import { spacing } from '@/theme';

export function HomeScreen({
  captures,
  error,
  isLoading,
  tileWidth,
  onOpenPaste,
  onOpenProfile,
  onOpenCapture,
  onRefresh,
}: {
  captures: Capture[];
  error: string | null;
  isLoading: boolean;
  tileWidth: number;
  onOpenPaste: () => void;
  onOpenProfile: () => void;
  onOpenCapture: (capture: Capture) => void;
  onRefresh: () => void;
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
        <Text style={styles.screenTitle}>Saved items</Text>
        <Text style={styles.screenSubtitle}>Items you have saved</Text>
      </View>

      {error ? <InlineMessage tone="error" message={error} actionLabel="Try again" onAction={onRefresh} /> : null}

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
    <View style={styles.grid}>
      <View style={[styles.reelSkeletonTile, styles.reelSkeletonTileFeatured, { width: tileWidth * 2 + spacing.md }]} />
      <View style={[styles.reelSkeletonTile, { width: tileWidth }]} />
      <View style={[styles.reelSkeletonTile, { width: tileWidth }]} />
    </View>
  );
}

function EmptyCaptures({ onOpenPaste }: { onOpenPaste: () => void }) {
  return (
    <View style={styles.stateCard}>
      <Text style={styles.stateTitle}>No saved items yet</Text>
      <Text style={styles.stateBody}>Share a Reel to Mentioned, or paste a link to start finding books.</Text>
      <View style={styles.emptyPreviewWrap}>
        <SourceToBooksPreview />
      </View>
      <View style={styles.stateActions}>
        <PrimaryButton label="Paste link" onPress={onOpenPaste} compact />
      </View>
    </View>
  );
}
