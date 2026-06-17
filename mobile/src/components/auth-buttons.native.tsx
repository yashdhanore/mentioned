import { ActivityIndicator, Platform, Pressable, Text, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';

import { styles } from '@/styles';

import type { AuthButtonsProps } from './auth-buttons';

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

function GoogleGlyph() {
  return (
    <Svg height={26} viewBox="0 0 48 48" width={26}>
      <Path
        d="M24 9.5c3.54 0 6.72 1.22 9.22 3.61l6.86-6.86C35.92 2.38 30.48 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
        fill="#EA4335"
      />
      <Path
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
        fill="#4285F4"
      />
      <Path
        d="M10.53 28.59A14.4 14.4 0 0 1 9.75 24c0-1.59.28-3.14.78-4.59l-7.98-6.19A23.88 23.88 0 0 0 0 24c0 3.87.93 7.54 2.56 10.78l7.97-6.19z"
        fill="#FBBC05"
      />
      <Path
        d="M24 48c6.48 0 11.93-2.13 15.89-5.8l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
        fill="#34A853"
      />
      <Path d="M0 0h48v48H0z" fill="none" />
    </Svg>
  );
}
