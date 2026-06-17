import type { ReactNode } from 'react';
import { Pressable, Text, View, type StyleProp, type ViewStyle } from 'react-native';
import Svg, { Path } from 'react-native-svg';

import { styles } from '@/styles';

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
  variant?: 'plain' | 'filled';
};

type SurfaceProps = {
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
  variant?: 'plain' | 'paper' | 'raised';
};

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
  variant = 'plain',
}: IconButtonProps) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      disabled={disabled}
      style={({ pressed }) => [
        styles.iconButton,
        variant === 'filled' && styles.iconButtonFilled,
        disabled && styles.disabledButton,
        pressed && styles.pressed,
      ]}
      onPress={onPress}
    >
      {typeof children === 'string' ? <Text style={styles.iconButtonText}>{children}</Text> : children}
    </Pressable>
  );
}

export function AppMark() {
  return (
    <View accessibilityLabel="Mentioned" accessibilityRole="image" style={styles.appMark}>
      <Svg height={32} viewBox="0 0 1024 1024" width={32}>
        <Path
          d="M300 300 L512 724 L724 300 L724 724"
          fill="none"
          stroke="#0E6F68"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={92}
        />
      </Svg>
    </View>
  );
}

export function Surface({ children, style, variant = 'plain' }: SurfaceProps) {
  return (
    <View
      style={[
        styles.surface,
        variant === 'paper' && styles.paperSurface,
        variant === 'raised' && styles.raisedSurface,
        style,
      ]}
    >
      {children}
    </View>
  );
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

export function SourceQuote({
  attribution,
  quote,
}: {
  attribution?: string | null;
  quote: string;
}) {
  return (
    <View style={styles.sourceQuote}>
      <View style={styles.sourceQuoteLine} />
      <View style={styles.sourceQuoteCopy}>
        <Text style={styles.sourceQuoteText}>{quote}</Text>
        {attribution ? <Text style={styles.sourceQuoteAttribution}>{attribution}</Text> : null}
      </View>
    </View>
  );
}

export function InlineMessage({
  message,
  tone,
  actionLabel,
  onAction,
}: {
  message: string;
  tone: 'error' | 'warning';
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <View style={[styles.inlineMessage, tone === 'error' ? styles.inlineError : styles.inlineWarning]}>
      <Text style={[styles.inlineMessageText, tone === 'error' ? styles.inlineErrorText : styles.inlineWarningText]}>
        {message}
      </Text>
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
