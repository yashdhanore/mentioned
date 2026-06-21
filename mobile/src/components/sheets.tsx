import type { ReactNode } from 'react';
import { useEffect, useRef, useState } from 'react';
import {
  Animated,
  Easing,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  Text,
  TextInput,
  View,
} from 'react-native';
import * as Linking from 'expo-linking';

import { styles } from '@/styles';
import { colors } from '@/theme';
import { InlineMessage, PrimaryButton } from '@/components/ui';

export function ProfileSheet({
  visible,
  accountLabel,
  error,
  isSigningOut,
  isDeletingAccount,
  confirmingDeleteAccount,
  onClose,
  onSignOut,
  onRequestDeleteAccount,
  onConfirmDeleteAccount,
  onCancelDeleteAccount,
  privacyPolicyUrl,
}: {
  visible: boolean;
  accountLabel: string;
  error: string | null;
  isSigningOut: boolean;
  isDeletingAccount: boolean;
  confirmingDeleteAccount: boolean;
  onClose: () => void;
  onSignOut: () => void;
  onRequestDeleteAccount: () => void;
  onConfirmDeleteAccount: () => void;
  onCancelDeleteAccount: () => void;
  privacyPolicyUrl: string | null;
}) {
  const busy = isSigningOut || isDeletingAccount;
  return (
    <BottomSheet visible={visible} onClose={onClose}>
      <Text style={styles.sheetTitle}>Profile</Text>
      <Text style={styles.accountEmail}>{accountLabel}</Text>
      {error ? <InlineMessage tone="error" message={error} /> : null}
      <View style={styles.sheetMenu}>
        {privacyPolicyUrl ? (
          <SheetRow label="Privacy Policy" onPress={() => void Linking.openURL(privacyPolicyUrl)} />
        ) : null}
        <SheetRow
          label={isSigningOut ? 'Signing out...' : 'Sign out'}
          onPress={onSignOut}
          disabled={busy}
        />
        {confirmingDeleteAccount ? null : (
          <SheetRow
            label="Delete account"
            destructive
            onPress={onRequestDeleteAccount}
            disabled={busy}
          />
        )}
      </View>
      {confirmingDeleteAccount ? (
        <>
          <View style={styles.sheetWarning}>
            <Text style={styles.sheetWarningTitle}>Delete account?</Text>
            <Text style={styles.sheetWarningBody}>
              This permanently deletes your account, saved posts, and books. This cannot be undone.
            </Text>
          </View>
          <View style={styles.sheetMenu}>
            <SheetRow
              label={isDeletingAccount ? 'Deleting account...' : 'Confirm delete account'}
              destructive
              onPress={onConfirmDeleteAccount}
              disabled={isDeletingAccount}
            />
            <SheetRow label="Cancel" onPress={onCancelDeleteAccount} disabled={isDeletingAccount} />
          </View>
        </>
      ) : null}
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
      <Text style={styles.sheetTitle}>Paste link</Text>
      <Text style={styles.sheetBody}>Use this when sharing from another app is not available.</Text>
      <Text style={styles.inputLabel}>Post URL</Text>
      <TextInput
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
        multiline
        numberOfLines={3}
        onChangeText={(text) => onChange(text.replace(/\n/g, ''))}
        placeholder="https://www.instagram.com/reel/..."
        placeholderTextColor={colors.onMuted}
        style={styles.input}
        textAlignVertical="top"
        value={value}
      />
      {error ? <InlineMessage tone="error" message={error} /> : null}
      <PrimaryButton
        label={isSubmitting ? 'Finding books...' : 'Find books'}
        onPress={onSubmit}
        disabled={isSubmitting}
      />
    </BottomSheet>
  );
}

export function ReelMenuSheet({
  visible,
  error,
  isDeleting,
  onClose,
  onDeletePost,
  onOpenSource,
}: {
  visible: boolean;
  error: string | null;
  isDeleting: boolean;
  onClose: () => void;
  onDeletePost?: () => void;
  onOpenSource?: () => void;
}) {
  return (
    <BottomSheet visible={visible} onClose={onClose}>
      <Text style={styles.sheetTitle}>Post actions</Text>
      {error ? <InlineMessage tone="error" message={error} /> : null}
      <View style={styles.sheetMenu}>
        <SheetRow
          label="Open original"
          disabled={isDeleting}
          onPress={() => {
            onOpenSource?.();
            onClose();
          }}
        />
        <SheetRow
          label={isDeleting ? 'Deleting...' : 'Delete post'}
          destructive
          disabled={isDeleting}
          onPress={onDeletePost}
        />
      </View>
    </BottomSheet>
  );
}

// A bottom sheet where the backdrop fades in place while only the card slides
// up. Built on RN's Animated (no deps). The KeyboardAvoidingView is the outer
// container so the whole card lifts above the keyboard instead of hiding behind
// it. The card height is measured so it can start fully off-screen regardless
// of its content.
const SHEET_FALLBACK_HEIGHT = 420;

function BottomSheet({
  visible,
  onClose,
  children,
}: {
  visible: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  // Keep the modal mounted through the exit animation, then unmount.
  const [mounted, setMounted] = useState(visible);
  const progress = useRef(new Animated.Value(0)).current;
  const cardHeight = useRef(SHEET_FALLBACK_HEIGHT);

  useEffect(() => {
    if (visible) {
      setMounted(true);
      Animated.timing(progress, {
        toValue: 1,
        duration: 250,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }).start();
      return;
    }
    Animated.timing(progress, {
      toValue: 0,
      duration: 200,
      easing: Easing.in(Easing.cubic),
      useNativeDriver: true,
    }).start(({ finished }) => {
      if (finished) {
        setMounted(false);
      }
    });
  }, [visible, progress]);

  if (!mounted) {
    return null;
  }

  const backdropOpacity = progress;
  const translateY = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [cardHeight.current, 0],
  });

  return (
    <Modal animationType="none" transparent visible onRequestClose={onClose}>
      <KeyboardAvoidingView
        style={styles.sheetContainer}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <Animated.View style={[styles.modalOverlay, { opacity: backdropOpacity }]}>
          <Pressable style={styles.modalOverlayFill} onPress={onClose} />
        </Animated.View>
        <Animated.View
          style={[styles.bottomSheet, { transform: [{ translateY }] }]}
          onLayout={(event) => {
            cardHeight.current = event.nativeEvent.layout.height;
          }}
        >
          <View style={styles.sheetHandle} />
          {children}
        </Animated.View>
      </KeyboardAvoidingView>
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
