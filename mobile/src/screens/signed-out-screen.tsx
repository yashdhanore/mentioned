import { StatusBar } from 'expo-status-bar';
import * as Linking from 'expo-linking';
import { Pressable, SafeAreaView, ScrollView, Text, View } from 'react-native';

import { SignedOutProductPreview } from '@/components/signed-out-product-preview';
import { AppMark, InlineMessage } from '@/components/ui';
import { styles } from '@/styles';

export function SignedOutScreen({
  error,
  pendingSharedSourceUrl,
  isGoogleLoading,
  isDisabled,
  onContinueGoogle,
  onDiscardPendingSharedSource,
  privacyPolicyUrl,
}: {
  error: string | null;
  pendingSharedSourceUrl: string | null;
  isGoogleLoading: boolean;
  isDisabled: boolean;
  onContinueGoogle: () => void;
  onDiscardPendingSharedSource: () => void;
  privacyPolicyUrl: string | null;
}) {
  const hasPendingSharedSource = pendingSharedSourceUrl !== null;

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <ScrollView
        contentContainerStyle={styles.authScreen}
        contentInsetAdjustmentBehavior="automatic"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.authTop}>
          <AppMark />
        </View>

        <View style={styles.authIntro}>
          <View style={styles.authCopy}>
            {hasPendingSharedSource ? (
              <Text style={styles.authTitle}>
                <Text style={styles.authTitleSlot}>1 Reel</Text> ready to save.
              </Text>
            ) : (
              <Text style={styles.authTitle}>
                Save the{'\n'}
                <Text style={styles.authTitleSlot}>books inside</Text>
                {'\n'}Reels.
              </Text>
            )}
            <Text style={styles.authBody}>
              {hasPendingSharedSource
                ? 'Continue to find the books inside and keep the source for later.'
                : 'Share a Reel, keep the source, find the books later.'}
            </Text>
          </View>

          {pendingSharedSourceUrl ? (
            <View style={styles.authPendingRow}>
              <View style={styles.authPendingCopy}>
                <Text style={styles.authPendingTitle}>Sign in to save this shared source.</Text>
                <Text ellipsizeMode="middle" numberOfLines={1} style={styles.authPendingUrl}>
                  {pendingSharedSourceUrl}
                </Text>
              </View>
              <Pressable
                accessibilityRole="button"
                style={({ pressed }) => [styles.authPendingAction, pressed && styles.pressed]}
                onPress={onDiscardPendingSharedSource}
              >
                <Text style={styles.authPendingActionText}>Discard</Text>
              </Pressable>
            </View>
          ) : null}

          {error ? <InlineMessage tone="error" message={error} /> : null}
          <GoogleSignInButton
            isLoading={isGoogleLoading}
            onPress={onContinueGoogle}
            disabled={isDisabled}
          />
        </View>

        <View style={styles.authPreviewWrap}>
          <SignedOutProductPreview />
        </View>

        <View style={styles.authFooter}>
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

function GoogleSignInButton({
  disabled,
  isLoading,
  onPress,
}: {
  disabled: boolean;
  isLoading: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ busy: isLoading, disabled }}
      disabled={disabled}
      style={({ pressed }) => [
        styles.authGoogleButton,
        disabled && styles.disabledButton,
        pressed && styles.pressed,
      ]}
      onPress={onPress}
    >
      <Text style={styles.authGoogleGlyphText}>G</Text>
      <Text style={styles.authGoogleButtonText}>
        {isLoading ? 'Signing in...' : 'Continue with Google'}
      </Text>
    </Pressable>
  );
}
