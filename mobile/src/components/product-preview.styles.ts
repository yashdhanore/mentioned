import { StyleSheet } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';

export const styles = StyleSheet.create({
  productPreview: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.sm,
    justifyContent: 'center',
  },
  previewReelCard: {
    aspectRatio: 0.62,
    backgroundColor: colors.book,
    borderColor: colors.hairline,
    borderRadius: radius.lg,
    borderWidth: 1,
    justifyContent: 'flex-end',
    overflow: 'hidden',
    padding: spacing.sm,
    width: 122,
  },
  previewImageWash: {
    backgroundColor: colors.secondary,
    bottom: 0,
    left: 0,
    opacity: 0.46,
    position: 'absolute',
    right: 0,
    top: 0,
  },
  previewScrim: {
    backgroundColor: colors.scrim,
    bottom: 0,
    height: '58%',
    left: 0,
    position: 'absolute',
    right: 0,
  },
  previewReelText: {
    ...typography.bodySm,
    color: colors.onPrimary,
  },
  previewCreator: {
    ...typography.caption,
    color: colors.onPrimary,
    marginTop: spacing.md,
    opacity: 0.82,
  },
  previewConnector: {
    alignItems: 'center',
    width: 22,
  },
  previewConnectorDot: {
    backgroundColor: colors.primary,
    borderRadius: 4,
    height: 8,
    width: 8,
  },
  previewConnectorLine: {
    backgroundColor: colors.primary,
    height: 70,
    opacity: 0.5,
    width: 1,
  },
  previewBookStack: {
    gap: spacing.sm,
    width: 166,
  },
  previewBookLabel: {
    ...typography.caption,
    color: colors.onMuted,
    textAlign: 'center',
  },
  previewBookRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.sm,
    padding: spacing.xs,
  },
  previewBookCopy: {
    flex: 1,
    gap: spacing.xs,
  },
  previewBookTitle: {
    ...typography.labelMd,
    color: colors.ink,
  },
  previewBookAuthor: {
    ...typography.caption,
    color: colors.inkMuted,
  },
});
