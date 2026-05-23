import { View, type StyleProp, type ViewStyle } from 'react-native';

import { styles } from '@/styles';

type IconProps = {
  color?: string;
  style?: StyleProp<ViewStyle>;
};

export function PlusIcon({ color = '#101A17', style }: IconProps) {
  return (
    <View style={[styles.iconCanvas, style]}>
      <View style={[styles.iconStroke, styles.iconPlusHorizontal, { backgroundColor: color }]} />
      <View style={[styles.iconStroke, styles.iconPlusVertical, { backgroundColor: color }]} />
    </View>
  );
}

export function UserIcon({ color = '#101A17', style }: IconProps) {
  return (
    <View style={[styles.iconCanvas, style]}>
      <View style={[styles.iconUserHead, { borderColor: color }]} />
      <View style={[styles.iconUserBody, { borderColor: color }]} />
    </View>
  );
}

export function BackIcon({ color = '#101A17', style }: IconProps) {
  return (
    <View style={[styles.iconCanvas, style]}>
      <View style={[styles.iconChevronLine, styles.iconChevronUpper, { backgroundColor: color }]} />
      <View style={[styles.iconChevronLine, styles.iconChevronLower, { backgroundColor: color }]} />
    </View>
  );
}

export function MoreIcon({ color = '#101A17', style }: IconProps) {
  return (
    <View style={[styles.iconCanvas, styles.iconMoreCanvas, style]}>
      <View style={[styles.iconDot, { backgroundColor: color }]} />
      <View style={[styles.iconDot, { backgroundColor: color }]} />
      <View style={[styles.iconDot, { backgroundColor: color }]} />
    </View>
  );
}

export function ExternalIcon({ color = '#0E6F68', style }: IconProps) {
  return (
    <View style={[styles.iconCanvas, style]}>
      <View style={[styles.iconExternalBox, { borderColor: color }]} />
      <View style={[styles.iconExternalStem, { backgroundColor: color }]} />
      <View style={[styles.iconExternalArrowA, { backgroundColor: color }]} />
      <View style={[styles.iconExternalArrowB, { backgroundColor: color }]} />
    </View>
  );
}
