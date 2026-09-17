import { Text, View } from 'react-native';

import { FadeInView } from '@/components/motion';
import { Tumbleweed } from '@/components/tumbleweed';
import { PrimaryButton } from '@/components/ui';
import { styles } from './empty-state.styles';

export function EmptyCaptures({ onOpenPaste }: { onOpenPaste: () => void }) {
  return (
    <FadeInView>
      <View style={styles.emptyScene}>
        <Tumbleweed />
        <Text style={styles.emptySceneTitle}>Sure looks empty out here</Text>
        <Text style={styles.emptySceneBody}>
          Share a reel and Mentioned will round up the books mentioned inside.
        </Text>
        <View style={styles.emptySceneActions}>
          <PrimaryButton label="Paste link" onPress={onOpenPaste} compact />
        </View>
      </View>
    </FadeInView>
  );
}
