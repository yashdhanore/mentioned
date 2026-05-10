import { Image, Pressable, Text, View } from 'react-native';

import type { Capture } from '@/captures';
import { styles } from '@/styles';

export function ReelTile({
  capture,
  width,
  onPress,
}: {
  capture: Capture;
  width: number;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${capture.creator} saved Reel`}
      style={({ pressed }) => [styles.reelTile, { width }, pressed && styles.pressed]}
      onPress={onPress}
    >
      <Image source={{ uri: capture.thumbnailUrl }} style={styles.reelTileImage} />
      <View style={styles.reelTileScrim} />
      {capture.status !== 'ready' ? <TileStatus status={capture.status} /> : null}
      <Text numberOfLines={1} style={styles.reelCreator}>
        {capture.creator}
      </Text>
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
