import { Image, Pressable, Text, View } from 'react-native';

import { captureStatusLabel, sourceIdentityLabel, type Capture } from '@/captures';
import { AppMark } from '@/components/ui';
import { styles as sharedStyles } from '@/styles';
import { styles as localStyles } from './reel-tile.styles';

const styles = { ...sharedStyles, ...localStyles };

export function ReelTile({
  capture,
  width,
  onPress,
}: {
  capture: Capture;
  width: number;
  onPress: () => void;
}) {
  const identityLabel = sourceIdentityLabel(capture);
  const statusLabel = captureStatusLabel(capture);

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${identityLabel}, ${statusLabel}`}
      style={({ pressed }) => [styles.reelTile, { width }, pressed && styles.pressed]}
      onPress={onPress}
    >
      {capture.thumbnailUrl ? (
        <Image source={{ uri: capture.thumbnailUrl }} style={styles.reelTileImage} />
      ) : (
        <View style={styles.thumbnailFallback}>
          <AppMark style={styles.thumbnailFallbackMark} />
        </View>
      )}
      <View style={styles.reelTileScrim} />
      {capture.status !== 'ready' ? <TileStatus status={capture.status} /> : null}
      <View style={styles.reelTileMeta}>
        <Text numberOfLines={1} style={styles.reelCreator}>
          {identityLabel}
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
