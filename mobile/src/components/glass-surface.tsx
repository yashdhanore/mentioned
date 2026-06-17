import { BlurView } from 'expo-blur';
import type { ReactNode } from 'react';
import { Platform, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

const supportsRichGlass =
  Platform.OS === 'ios' && Number.parseInt(String(Platform.Version), 10) >= 26;

export function GlassSurface({
  children,
  style,
  fallbackStyle,
}: {
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
  fallbackStyle?: StyleProp<ViewStyle>;
}) {
  if (supportsRichGlass) {
    return (
      <BlurView intensity={40} tint="light" style={[styles.glass, style]}>
        {children}
      </BlurView>
    );
  }

  return <View style={[style, fallbackStyle]}>{children}</View>;
}

const styles = StyleSheet.create({
  glass: {
    overflow: 'hidden',
  },
});
