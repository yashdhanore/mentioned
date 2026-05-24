import { StatusBar } from 'expo-status-bar';
import * as Linking from 'expo-linking';
import { Pressable, SafeAreaView, ScrollView, Text, View } from 'react-native';

import { SourceToBooksPreview } from '@/components/product-preview';
import { AppMark, GoogleButton, InlineMessage } from '@/components/ui';
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
      <ScrollView contentContainerStyle={styles.authScreen} showsVerticalScrollIndicator={false}>
        <AppMark />

        <View style={styles.authHero}>
          <View style={styles.authCopy}>
            <Text style={styles.authBrand}>Mentioned</Text>
            <Text style={styles.authTitle}>
              Don't lose the <Text style={styles.authTitleSlot}>books</Text> that were mentioned.
            </Text>
            <Text style={styles.authBody}>Share a Reel, keep the source, find it later.</Text>
          </View>

          <View style={styles.authPreviewWrap}>
            <SourceToBooksPreview />
          </View>
        </View>

        <View style={styles.authActions}>
          {error ? <InlineMessage tone="error" message={error} /> : null}
          <GoogleButton
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
      </ScrollView>
    </SafeAreaView>
  );
}
