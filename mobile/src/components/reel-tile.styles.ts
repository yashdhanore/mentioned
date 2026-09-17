import { StyleSheet } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';

export const styles = StyleSheet.create({
  reelTile: {
    aspectRatio: 0.72,
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderRadius: radius.lg,
    borderWidth: 1,
    overflow: 'hidden',
  },
  reelTileFeatured: {
    aspectRatio: 1.46,
  },
  reelTileImage: {
    height: '100%',
    width: '100%',
  },
  reelTileScrim: {
    backgroundColor: 'rgba(16, 26, 23, 0.42)',
    bottom: 0,
    height: '54%',
    left: 0,
    position: 'absolute',
    right: 0,
  },
  latestBadge: {
    backgroundColor: colors.primary,
    borderRadius: 999,
    left: spacing.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    position: 'absolute',
    top: spacing.sm,
  },
  latestBadgeText: {
    ...typography.labelMd,
    color: colors.onPrimary,
  },
  reelTileMeta: {
    bottom: spacing.md,
    gap: spacing.sm,
    left: spacing.md,
    position: 'absolute',
    right: spacing.md,
  },
  reelTileTitle: {
    ...typography.titleMd,
    color: colors.onPrimary,
  },
  reelCreator: {
    ...typography.caption,
    color: colors.onPrimary,
    opacity: 0.82,
  },
  processingDot: {
    backgroundColor: colors.warningSoft,
    borderColor: colors.warning,
    borderRadius: 9,
    borderWidth: 1,
    height: 18,
    position: 'absolute',
    right: spacing.sm,
    top: spacing.sm,
    width: 18,
  },
  attentionDot: {
    alignItems: 'center',
    backgroundColor: colors.errorSoft,
    borderColor: colors.error,
    borderRadius: 9,
    borderWidth: 1,
    height: 18,
    justifyContent: 'center',
    position: 'absolute',
    right: spacing.sm,
    top: spacing.sm,
    width: 18,
  },
  attentionText: {
    color: colors.error,
    fontSize: 11,
    fontWeight: '700',
    lineHeight: 13,
  },
});
