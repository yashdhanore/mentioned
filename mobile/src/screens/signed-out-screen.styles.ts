import { StyleSheet } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';

export const styles = StyleSheet.create({
  authTop: {
    alignItems: 'flex-start',
    paddingTop: spacing.sm,
  },
  authCopy: {
    gap: spacing.lg,
  },
  authIntro: {
    gap: spacing.lg,
    paddingTop: spacing.xl,
  },
  authTitle: {
    fontSize: 46,
    fontWeight: '400',
    letterSpacing: 0,
    lineHeight: 52,
    color: colors.onSurface,
    maxWidth: 318,
  },
  authTitleSlot: {
    color: colors.onSurface,
  },
  authBody: {
    fontSize: 16,
    fontWeight: '400',
    letterSpacing: 0,
    lineHeight: 23,
    color: colors.onMuted,
    maxWidth: 292,
  },
  authPreviewWrap: {
    alignItems: 'center',
    overflow: 'hidden',
    paddingTop: spacing.sm,
    width: '100%',
  },
  authPendingRow: {
    alignItems: 'center',
    alignSelf: 'flex-start',
    borderRadius: radius.md,
    flexDirection: 'row',
    gap: spacing.md,
    maxWidth: 292,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  authPendingRowFallback: {
    borderColor: colors.border,
    borderWidth: 1,
  },
  authPendingCopy: {
    flex: 1,
    gap: spacing.xxs,
    minWidth: 0,
  },
  authPendingTitle: {
    ...typography.labelMd,
    color: colors.secondary,
  },
  authPendingUrl: {
    ...typography.caption,
    color: colors.onMuted,
  },
  authPendingAction: {
    paddingHorizontal: spacing.xs,
    paddingVertical: spacing.xs,
  },
  authPendingActionText: {
    ...typography.labelMd,
    color: colors.primary,
  },
  authFooter: {
    alignItems: 'center',
    marginTop: 'auto',
  },
  authLink: {
    alignSelf: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  authLinkText: {
    ...typography.labelMd,
    color: colors.secondary,
  },
});
