import { StatusBar } from 'expo-status-bar';
import { SafeAreaView, Text, View } from 'react-native';

import { InlineMessage, PrimaryButton, SecondaryButton } from '@/components/ui';
import { styles } from '@/styles';

export function SignedOutScreen({
  error,
  isAppleLoading,
  isGoogleLoading,
  isDisabled,
  onContinueApple,
  onContinueGoogle,
}: {
  error: string | null;
  isAppleLoading: boolean;
  isGoogleLoading: boolean;
  isDisabled: boolean;
  onContinueApple: () => void;
  onContinueGoogle: () => void;
}) {
  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <View style={styles.authScreen}>
        <View style={styles.authMark}>
          <Text style={styles.authMarkText}>M</Text>
        </View>
        <View style={styles.authCopy}>
          <Text style={styles.authBrand}>Mentioned</Text>
          <Text style={styles.authTitle}>Save Reels and see the books mentioned inside them.</Text>
          <Text style={styles.authBody}>
            Share a Reel to Mentioned. We keep the source with the books it mentions, so you can find
            them later.
          </Text>
        </View>
        <View style={styles.authActions}>
          {error ? <InlineMessage tone="error" message={error} /> : null}
          <PrimaryButton
            label={isAppleLoading ? 'Signing in...' : 'Continue with Apple'}
            onPress={onContinueApple}
            disabled={isDisabled}
          />
          <SecondaryButton
            label={isGoogleLoading ? 'Signing in...' : 'Continue with Google'}
            onPress={onContinueGoogle}
            disabled={isDisabled}
          />
        </View>
      </View>
    </SafeAreaView>
  );
}
