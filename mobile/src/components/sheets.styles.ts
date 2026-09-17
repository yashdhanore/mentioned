import { StyleSheet } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';

export const styles = StyleSheet.create({
  sheetContainer: {
    flex: 1,
    justifyContent: 'flex-end',
  },
  modalOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(20, 32, 27, 0.35)',
  },
  modalOverlayFill: {
    flex: 1,
  },
  bottomSheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    gap: spacing.lg,
    padding: spacing.screen,
    paddingBottom: spacing.xxl,
  },
  sheetHandle: {
    alignSelf: 'center',
    backgroundColor: colors.border,
    borderRadius: 2,
    height: 4,
    width: 42,
  },
  sheetTitle: {
    ...typography.headlineMd,
    color: colors.onSurface,
  },
  sheetBody: {
    ...typography.bodySm,
    color: colors.onMuted,
  },
  accountEmail: {
    ...typography.bodySm,
    color: colors.onMuted,
  },
  sheetMenu: {
    borderColor: colors.border,
    borderRadius: radius.md,
    borderWidth: 1,
    overflow: 'hidden',
  },
  sheetWarning: {
    backgroundColor: colors.errorSoft,
    borderRadius: radius.md,
    gap: spacing.xs,
    padding: spacing.md,
  },
  sheetWarningTitle: {
    ...typography.labelLg,
    color: colors.error,
  },
  sheetWarningBody: {
    ...typography.bodySm,
    color: colors.onSurface,
  },
  sheetRow: {
    backgroundColor: colors.surface,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    minHeight: 48,
    justifyContent: 'center',
    paddingHorizontal: spacing.md,
  },
  sheetRowText: {
    ...typography.bodyMd,
    color: colors.onSurface,
  },
  destructiveText: {
    color: colors.error,
  },
  inputLabel: {
    ...typography.labelMd,
    color: colors.secondary,
    marginBottom: spacing.xs,
    marginTop: spacing.sm,
  },
  input: {
    ...typography.bodyMd,
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderRadius: radius.md,
    borderWidth: 1,
    color: colors.onSurface,
    minHeight: 48,
    maxHeight: 96,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginBottom: spacing.lg,
  },
});
