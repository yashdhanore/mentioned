import { ActivityIndicator, Platform, Pressable, Text, View } from 'react-native';

import { GoogleGlyph } from '@/components/google-glyph';
import { styles as sharedStyles } from '@/styles';
import { styles as localStyles } from './auth-buttons.styles';
import type { AuthButtonsProps } from './auth-buttons';

const styles = { ...sharedStyles, ...localStyles };

export function AuthButtons({
  isAppleLoading,
  isDisabled,
  onContinueApple,
  onContinueGoogle,
}: AuthButtonsProps) {
  return (
    <View
      accessibilityState={{ busy: isDisabled }}
      pointerEvents={isDisabled ? 'none' : 'auto'}
      style={[styles.authProviderGroup, isDisabled && styles.authProviderGroupBusy]}
    >
      {Platform.OS === 'ios' ? (
        <Pressable
          accessibilityRole="button"
          accessibilityState={{ busy: isAppleLoading, disabled: isDisabled }}
          disabled={isDisabled}
          style={({ pressed }) => [
            styles.authWebButton,
            styles.authWebButtonApple,
            isDisabled && styles.disabledButton,
            pressed && styles.pressed,
          ]}
          onPress={onContinueApple}
        >
          <View style={styles.authWebAppleContent}>
            <Text style={styles.authWebAppleGlyph}>{'\uF8FF'}</Text>
            <Text style={styles.authWebButtonText}>Continue with Apple</Text>
          </View>
        </Pressable>
      ) : null}
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ busy: isDisabled && !isAppleLoading, disabled: isDisabled }}
        disabled={isDisabled}
        style={({ pressed }) => [
          styles.authWebButton,
          styles.authWebButtonGoogle,
          isDisabled && styles.disabledButton,
          pressed && styles.pressed,
        ]}
        onPress={onContinueGoogle}
      >
        <View style={styles.authWebGoogleIconWell}>
          <GoogleGlyph />
        </View>
        <Text style={styles.authWebButtonText}>Continue with Google</Text>
      </Pressable>
      {isDisabled ? (
        <View pointerEvents="none" style={styles.authProviderOverlay}>
          <ActivityIndicator
            accessibilityLabel={isAppleLoading ? 'Signing in with Apple' : 'Signing in with Google'}
          />
        </View>
      ) : null}
    </View>
  );
}
