import { StyleSheet } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';

export const styles = StyleSheet.create({
  surface: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.md,
    borderWidth: 1,
  },
  paperSurface: {
    backgroundColor: colors.paper,
    borderColor: colors.paperEdge,
  },
  raisedSurface: {
    backgroundColor: colors.surfaceElevated,
  },
  appMark: {
    alignItems: 'center',
    alignSelf: 'flex-start',
    height: 42,
    justifyContent: 'center',
    width: 42,
  },
  iconButton: {
    alignItems: 'center',
    backgroundColor: colors.surfaceElevated,
    borderColor: colors.border,
    borderRadius: 20,
    borderWidth: 1,
    height: 40,
    justifyContent: 'center',
    width: 40,
  },
  iconButtonFilled: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  iconButtonText: {
    ...typography.labelLg,
    color: colors.ink,
    lineHeight: 18,
  },
  sourceQuote: {
    backgroundColor: colors.sourceContextSoft,
    borderColor: colors.border,
    borderRadius: radius.md,
    borderWidth: 1,
    flexDirection: 'row',
    gap: spacing.md,
    padding: spacing.md,
  },
  sourceQuoteLine: {
    backgroundColor: colors.primary,
    borderRadius: 1,
    width: 2,
  },
  sourceQuoteCopy: {
    flex: 1,
    gap: spacing.xs,
  },
  sourceQuoteText: {
    ...typography.bodySm,
    color: colors.ink,
  },
  sourceQuoteAttribution: {
    ...typography.caption,
    color: colors.sourceContext,
  },
  bookSpineText: {
    ...typography.labelMd,
    color: colors.onPrimary,
    textAlign: 'center',
  },
  bookSpineSkeleton: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.sm,
    height: 74,
    width: 52,
  },
  primaryButton: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    minHeight: 52,
    justifyContent: 'center',
    paddingHorizontal: spacing.lg,
  },
  primaryButtonText: {
    ...typography.labelLg,
    color: colors.onPrimary,
  },
  secondaryButton: {
    alignItems: 'center',
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderRadius: radius.md,
    borderWidth: 1,
    minHeight: 48,
    justifyContent: 'center',
    paddingHorizontal: spacing.lg,
  },
  secondaryButtonText: {
    ...typography.labelLg,
    color: colors.onSurface,
  },
  compactButton: {
    minHeight: 40,
    paddingHorizontal: spacing.md,
  },
  inlineMessage: {
    borderRadius: radius.md,
    borderWidth: 1,
    gap: spacing.sm,
    padding: spacing.md,
  },
  inlineError: {
    backgroundColor: colors.errorSoft,
    borderColor: colors.error,
  },
  inlineWarning: {
    backgroundColor: colors.warningSoft,
    borderColor: colors.warning,
  },
  inlineMessageText: {
    ...typography.bodySm,
  },
  inlineErrorText: {
    color: colors.error,
  },
  inlineWarningText: {
    color: colors.warning,
  },
  inlineAction: {
    alignSelf: 'flex-start',
  },
  inlineActionText: {
    ...typography.labelMd,
    color: colors.primary,
  },
});
