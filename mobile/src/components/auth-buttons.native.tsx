import { GoogleSigninButton } from '@react-native-google-signin/google-signin';
import * as AppleAuthentication from 'expo-apple-authentication';
import { ActivityIndicator, Platform, View } from 'react-native';

import { styles } from '@/styles';
import { radius } from '@/theme';

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
        <AppleAuthentication.AppleAuthenticationButton
          buttonType={AppleAuthentication.AppleAuthenticationButtonType.CONTINUE}
          buttonStyle={AppleAuthentication.AppleAuthenticationButtonStyle.BLACK}
          cornerRadius={radius.md}
          style={styles.authAppleNativeButton}
          onPress={onContinueApple}
        />
      ) : null}
      <GoogleSigninButton
        size={GoogleSigninButton.Size.Wide}
        color={GoogleSigninButton.Color.Dark}
        disabled={isDisabled}
        style={styles.authGoogleNativeButton}
        onPress={onContinueGoogle}
      />
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
