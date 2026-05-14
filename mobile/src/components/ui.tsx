import { Pressable, Text, View } from 'react-native';

import { styles } from '@/styles';

type ButtonProps = {
  label: string;
  onPress: () => void;
  compact?: boolean;
  disabled?: boolean;
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
