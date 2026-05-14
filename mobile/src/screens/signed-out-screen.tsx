import { StatusBar } from 'expo-status-bar';
import * as Linking from 'expo-linking';
import { Pressable, SafeAreaView, Text, View } from 'react-native';

import { InlineMessage, PrimaryButton } from '@/components/ui';
import { styles } from '@/styles';

export function SignedOutScreen({
  error,
  isGoogleLoading,
  isDisabled,
  onContinueGoogle,
  privacyPolicyUrl,
}: {
  error: string | null;
  isGoogleLoading: boolean;
  isDisabled: boolean;
  onContinueGoogle: () => void;
  privacyPolicyUrl: string | null;
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
            label={isGoogleLoading ? 'Signing in...' : 'Continue with Google'}
            onPress={onContinueGoogle}
            disabled={isDisabled}
          />
          {privacyPolicyUrl ? (
            <Pressable
              accessibilityRole="link"
              style={({ pressed }) => [styles.authLink, pressed && styles.pressed]}
              onPress={() => void Linking.openURL(privacyPolicyUrl)}
            >
              <Text style={styles.authLinkText}>Privacy Policy</Text>
            </Pressable>
          ) : null}
        </View>
      </View>
    </SafeAreaView>
  );
}
