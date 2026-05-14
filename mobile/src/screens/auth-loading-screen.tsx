import { StatusBar } from 'expo-status-bar';
import { ActivityIndicator, SafeAreaView, View } from 'react-native';

import { styles } from '@/styles';
import { colors } from '@/theme';

export function AuthLoadingScreen() {
  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <View style={styles.authScreen}>
        <ActivityIndicator color={colors.primary} />
      </View>
    </SafeAreaView>
  );
}
