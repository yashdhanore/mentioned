import type { ReactNode } from 'react';
import { Pressable, Text, View, type StyleProp, type ViewStyle } from 'react-native';
import Svg, { Path } from 'react-native-svg';

import { styles as sharedStyles } from '@/styles';
import { colors } from '@/theme';
import { styles as localStyles } from './ui.styles';

const styles = { ...sharedStyles, ...localStyles };

type ButtonProps = {
  label: string;
  onPress: () => void;
  compact?: boolean;
  disabled?: boolean;
};

type IconButtonProps = {
  accessibilityLabel: string;
  children: ReactNode;
  onPress: () => void;
  disabled?: boolean;
};

type SurfaceProps = {
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
};

type AppMarkProps = {
  size?: number;
  style?: StyleProp<ViewStyle>;
};

const COMPACT_BUTTON_HIT_SLOP = { top: 2, bottom: 2, left: 0, right: 0 };

export function PrimaryButton({
  label,
  onPress,
  compact = false,
  disabled = false,
}: ButtonProps) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      hitSlop={compact ? COMPACT_BUTTON_HIT_SLOP : undefined}
      style={({ pressed }) => [
        styles.primaryButton,
        compact && styles.compactButton,
        disabled && styles.disabledButton,
        pressed && styles.pressed,
      ]}
      onPress={onPress}
    >
      <Text style={styles.primaryButtonText}>{label}</Text>
    </Pressable>
  );
}

export function SecondaryButton({
  label,
  onPress,
  compact = false,
  disabled = false,
}: ButtonProps) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      hitSlop={compact ? COMPACT_BUTTON_HIT_SLOP : undefined}
      style={({ pressed }) => [
        styles.secondaryButton,
        compact && styles.compactButton,
        disabled && styles.disabledButton,
        pressed && styles.pressed,
      ]}
      onPress={onPress}
    >
      <Text style={styles.secondaryButtonText}>{label}</Text>
    </Pressable>
  );
}

export function IconButton({
  accessibilityLabel,
  children,
  disabled = false,
  onPress,
}: IconButtonProps) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      disabled={disabled}
      hitSlop={2}
      style={({ pressed }) => [
        styles.iconButton,
        disabled && styles.disabledButton,
        pressed && styles.pressed,
      ]}
      onPress={onPress}
    >
      {children}
    </Pressable>
  );
}

export function AppMark({ size = 32, style }: AppMarkProps = {}) {
  return (
    <View accessibilityLabel="Mentioned" accessibilityRole="image" style={[styles.appMark, style]}>
      <Svg height={size} viewBox="0 0 1024 1024" width={size}>
        <Path
          d="M300 300 L512 724 L724 300 L724 724"
          fill="none"
          stroke={colors.primary}
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={92}
        />
      </Svg>
    </View>
  );
}

export function Surface({ children, style }: SurfaceProps) {
  return <View style={[styles.surface, style]}>{children}</View>;
}

export function BookSpine({
  color,
  initials,
  title,
}: {
  color?: string;
  initials: string;
  title?: string;
}) {
  return (
    <View style={[styles.bookSpine, color ? { backgroundColor: color } : null]}>
      <Text numberOfLines={2} style={styles.bookSpineText}>
        {title || initials}
      </Text>
    </View>
  );
}

export function BookSpineSkeleton() {
  return <View style={styles.bookSpineSkeleton} />;
}

export function InlineMessage({
  message,
  actionLabel,
  onAction,
}: {
  message: string;
  tone: 'error';
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <View
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
      style={[styles.inlineMessage, styles.inlineError]}
    >
      <Text style={[styles.inlineMessageText, styles.inlineErrorText]}>{message}</Text>
      {actionLabel && onAction ? (
        <Pressable
          accessibilityRole="button"
          style={({ pressed }) => [styles.inlineAction, pressed && styles.pressed]}
          onPress={onAction}
        >
          <Text style={styles.inlineActionText}>{actionLabel}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}
