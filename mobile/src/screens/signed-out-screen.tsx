import { StatusBar } from 'expo-status-bar';
import * as Linking from 'expo-linking';
import { Pressable, SafeAreaView, ScrollView, Text, View } from 'react-native';

import { AuthButtons } from '@/components/auth-buttons';
import { SignedOutProductPreview } from '@/components/signed-out-product-preview';
import { GlassSurface } from '@/components/glass-surface';
import { AppMark, InlineMessage } from '@/components/ui';
import { styles as sharedStyles } from '@/styles';
import { styles as localStyles } from './signed-out-screen.styles';

const styles = { ...sharedStyles, ...localStyles };

export function SignedOutScreen({
  error,
  pendingSharedSourceUrl,
  isAppleLoading,
  isDisabled,
  onContinueGoogle,
  onContinueApple,
  onDiscardPendingSharedSource,
  privacyPolicyUrl,
}: {
  error: string | null;
  pendingSharedSourceUrl: string | null;
  isAppleLoading: boolean;
  isDisabled: boolean;
  onContinueGoogle: () => void;
  onContinueApple: () => void;
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
                <Text style={styles.authTitleSlot}>1 post</Text> ready to save.
              </Text>
            ) : (
              <Text style={styles.authTitle}>
                Save the{'\n'}
                <Text style={styles.authTitleSlot}>books inside</Text>
                {'\n'}posts.
              </Text>
            )}
            <Text style={styles.authBody}>
              {hasPendingSharedSource
                ? 'Continue to find the books inside and keep the post for later.'
                : 'Share a post, keep it here, find the books later.'}
            </Text>
          </View>

          {pendingSharedSourceUrl ? (
            <GlassSurface
              style={styles.authPendingRow}
              fallbackStyle={styles.authPendingRowFallback}
            >
              <View style={styles.authPendingCopy}>
                <Text style={styles.authPendingTitle}>Sign in to save this shared post.</Text>
                <Text ellipsizeMode="middle" numberOfLines={1} style={styles.authPendingUrl}>
                  {pendingSharedSourceUrl}
                </Text>
              </View>
              <Pressable
                accessibilityRole="button"
                hitSlop={{ top: 11, bottom: 11, left: 4, right: 4 }}
                style={({ pressed }) => [styles.authPendingAction, pressed && styles.pressed]}
                onPress={onDiscardPendingSharedSource}
              >
                <Text style={styles.authPendingActionText}>Discard</Text>
              </Pressable>
            </GlassSurface>
          ) : null}

          {error ? <InlineMessage message={error} /> : null}
          <AuthButtons
            isAppleLoading={isAppleLoading}
            isDisabled={isDisabled}
            onContinueApple={onContinueApple}
            onContinueGoogle={onContinueGoogle}
          />
        </View>

        <View style={styles.authPreviewWrap}>
          <SignedOutProductPreview />
        </View>

        <View style={styles.authFooter}>
          {privacyPolicyUrl ? (
            <Pressable
              accessibilityRole="link"
              hitSlop={{ top: 11, bottom: 11, left: 4, right: 4 }}
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
