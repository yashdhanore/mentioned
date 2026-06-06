import type { ReactNode } from 'react';
import {
  KeyboardAvoidingView,
  Modal,
  Pressable,
  Text,
  TextInput,
  View,
} from 'react-native';
import * as Linking from 'expo-linking';

import type { BookMention } from '@/captures';
import { styles } from '@/styles';
import { colors } from '@/theme';
import { InlineMessage, PrimaryButton } from '@/components/ui';

export function ProfileSheet({
  visible,
  accountLabel,
  error,
  isSigningOut,
  onClose,
  onSignOut,
  privacyPolicyUrl,
}: {
  visible: boolean;
  accountLabel: string;
  error: string | null;
  isSigningOut: boolean;
  onClose: () => void;
  onSignOut: () => void;
  privacyPolicyUrl: string | null;
}) {
  return (
    <BottomSheet visible={visible} onClose={onClose}>
      <Text style={styles.sheetTitle}>Profile</Text>
      <Text style={styles.accountEmail}>{accountLabel}</Text>
      {error ? <InlineMessage tone="error" message={error} /> : null}
      <View style={styles.sheetMenu}>
        {privacyPolicyUrl ? (
          <SheetRow label="Privacy Policy" onPress={() => void Linking.openURL(privacyPolicyUrl)} />
        ) : null}
        <SheetRow label={isSigningOut ? 'Signing out...' : 'Sign out'} onPress={onSignOut} disabled={isSigningOut} />
      </View>
    </BottomSheet>
  );
}

export function PasteSheet({
  visible,
  error,
  isSubmitting,
  value,
  onChange,
  onClose,
  onSubmit,
}: {
  visible: boolean;
  error: string | null;
  isSubmitting: boolean;
  value: string;
  onChange: (value: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  return (
    <BottomSheet visible={visible} onClose={onClose}>
      <KeyboardAvoidingView behavior={process.env.EXPO_OS === 'ios' ? 'padding' : undefined}>
        <Text style={styles.sheetTitle}>Paste link</Text>
        <Text style={styles.sheetBody}>Use this when sharing from another app is not available.</Text>
        <Text style={styles.inputLabel}>Post URL</Text>
        <TextInput
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
          onChangeText={onChange}
          placeholder="https://www.instagram.com/reel/..."
          placeholderTextColor={colors.onMuted}
          style={styles.input}
          value={value}
        />
        {error ? <InlineMessage tone="error" message={error} /> : null}
        <PrimaryButton
          label={isSubmitting ? 'Finding books...' : 'Find books'}
          onPress={onSubmit}
          disabled={isSubmitting}
        />
      </KeyboardAvoidingView>
    </BottomSheet>
  );
}

export function ReelMenuSheet({
  visible,
  onClose,
  onOpenSource,
}: {
  visible: boolean;
  onClose: () => void;
  onOpenSource?: () => void;
}) {
  return (
    <BottomSheet visible={visible} onClose={onClose}>
      <Text style={styles.sheetTitle}>Post actions</Text>
      <View style={styles.sheetMenu}>
        <SheetRow
          label="Open original"
          onPress={() => {
            onOpenSource?.();
            onClose();
          }}
        />
      </View>
    </BottomSheet>
  );
}

export function RemoveBookSheet({
  visible,
  book,
  error,
  isRemoving,
  onClose,
  onRemove,
}: {
  visible: boolean;
  book: BookMention | null;
  error: string | null;
  isRemoving: boolean;
  onClose: () => void;
  onRemove: () => void;
}) {
  return (
    <BottomSheet visible={visible} onClose={onClose}>
      <Text style={styles.sheetTitle}>Remove book</Text>
      <Text style={styles.sheetBody}>Remove this book from the saved post.</Text>
      {book ? (
        <View style={styles.sheetBookSummary}>
          <Text style={styles.sheetBookTitle}>{book.title}</Text>
          {book.author ? <Text style={styles.sheetBookAuthor}>{book.author}</Text> : null}
        </View>
      ) : null}
      {error ? <InlineMessage tone="error" message={error} /> : null}
      <View style={styles.sheetMenu}>
        <SheetRow
          label={isRemoving ? 'Removing...' : 'Remove book'}
          destructive
          disabled={isRemoving || !book}
          onPress={onRemove}
        />
      </View>
    </BottomSheet>
  );
}

function BottomSheet({
  visible,
  onClose,
  children,
}: {
  visible: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <Modal animationType="slide" transparent visible={visible} onRequestClose={onClose}>
      <Pressable style={styles.modalOverlay} onPress={onClose}>
        <Pressable style={styles.bottomSheet}>
          <View style={styles.sheetHandle} />
          {children}
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function SheetRow({
  label,
  destructive = false,
  disabled = false,
  onPress,
}: {
  label: string;
  destructive?: boolean;
  disabled?: boolean;
  onPress?: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled || !onPress}
      style={({ pressed }) => [styles.sheetRow, disabled && styles.disabledButton, pressed && styles.pressed]}
      onPress={onPress}
    >
      <Text style={[styles.sheetRowText, destructive && styles.destructiveText]}>{label}</Text>
    </Pressable>
  );
}
