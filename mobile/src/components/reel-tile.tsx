import { Image, Pressable, Text, View } from 'react-native';

import type { Capture } from '@/captures';
import { styles } from '@/styles';

export function ReelTile({
  capture,
  featured = false,
  width,
  onPress,
}: {
  capture: Capture;
  featured?: boolean;
  width: number;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={capture.creator}
      style={({ pressed }) => [
        styles.reelTile,
        featured && styles.reelTileFeatured,
        { width },
        pressed && styles.pressed,
      ]}
      onPress={onPress}
    >
      <Image source={{ uri: capture.thumbnailUrl }} style={styles.reelTileImage} />
      <View style={styles.reelTileScrim} />
      {featured ? (
        <View style={styles.latestBadge}>
          <Text style={styles.latestBadgeText}>Latest</Text>
        </View>
      ) : null}
      {capture.status !== 'ready' ? <TileStatus status={capture.status} /> : null}
      <View style={styles.reelTileMeta}>
        {capture.sourceContextSnippet ? (
          <Text numberOfLines={featured ? 2 : 1} style={styles.reelTileTitle}>
            {capture.sourceContextSnippet}
          </Text>
        ) : null}
        <Text numberOfLines={1} style={styles.reelCreator}>
          {capture.creator}
        </Text>
      </View>
    </Pressable>
  );
}

function TileStatus({ status }: { status: Capture['status'] }) {
  if (status === 'processing') {
    return <View accessibilityLabel="Processing" style={styles.processingDot} />;
  }

  return (
    <View accessibilityLabel="Needs attention" style={styles.attentionDot}>
      <Text style={styles.attentionText}>!</Text>
    </View>
  );
}
