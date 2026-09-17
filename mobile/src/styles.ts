import { StyleSheet } from 'react-native';

import { colors, radius, spacing } from '@/theme';

export const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.neutral,
  },
  pressed: {
    transform: [{ scale: 0.98 }],
    opacity: 0.88,
  },
  authScreen: {
    alignSelf: 'center',
    flexGrow: 1,
    gap: spacing.md,
    maxWidth: 430,
    paddingHorizontal: spacing.screen,
    paddingTop: spacing.md,
    paddingBottom: spacing.lg,
    width: '100%',
  },
  thumbnailFallback: {
    alignItems: 'center',
    height: '100%',
    justifyContent: 'center',
    width: '100%',
  },
  thumbnailFallbackMark: {
    alignSelf: 'center',
  },
  bookSpine: {
    alignItems: 'center',
    borderColor: colors.hairline,
    borderRadius: radius.sm,
    borderWidth: 1,
    height: 74,
    justifyContent: 'center',
    paddingHorizontal: spacing.xs,
    width: 52,
  },
  disabledButton: {
    opacity: 0.55,
  },
});
