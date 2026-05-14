import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';

import type { Capture } from '@/captures';
import { ReelTile } from '@/components/reel-tile';
import { InlineMessage, PrimaryButton } from '@/components/ui';
import { styles } from '@/styles';
import { colors } from '@/theme';

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
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Paste link"
            style={({ pressed }) => [styles.navSquareButton, pressed && styles.pressed]}
            onPress={onOpenPaste}
          >
            <Text style={styles.navButtonText}>+</Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Open profile and settings"
            style={({ pressed }) => [styles.profileButton, pressed && styles.pressed]}
            onPress={onOpenProfile}
          >
            <Text style={styles.profileButtonText}>Y</Text>
          </Pressable>
        </View>
      </View>

      <View style={styles.homeHeader}>
        <Text style={styles.screenTitle}>Saved Reels</Text>
        <Text style={styles.screenSubtitle}>Shared sources you want to return to.</Text>
      </View>

      {error ? <InlineMessage tone="error" message={error} actionLabel="Try again" onAction={onRefresh} /> : null}

      {isLoading && captures.length === 0 ? <LoadingState /> : null}
      {!isLoading && captures.length === 0 ? <EmptyCaptures onOpenPaste={onOpenPaste} /> : null}

      {captures.length > 0 ? (
        <View style={styles.grid}>
          {captures.map((capture) => (
            <ReelTile
              key={capture.id}
              capture={capture}
              width={tileWidth}
              onPress={() => onOpenCapture(capture)}
            />
          ))}
        </View>
      ) : null}
    </ScrollView>
  );
}

function LoadingState() {
  return (
    <View style={styles.loadingState}>
      <ActivityIndicator color={colors.primary} />
      <Text style={styles.loadingText}>Loading saved Reels...</Text>
    </View>
  );
}

function EmptyCaptures({ onOpenPaste }: { onOpenPaste: () => void }) {
  return (
    <View style={styles.stateCard}>
      <Text style={styles.stateTitle}>No saved Reels yet</Text>
      <Text style={styles.stateBody}>Paste an Instagram Reel or post link to start finding books.</Text>
      <View style={styles.stateActions}>
        <PrimaryButton label="Paste link" onPress={onOpenPaste} compact />
      </View>
    </View>
  );
}
