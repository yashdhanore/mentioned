import { StyleSheet } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';

export const styles = StyleSheet.create({
  topNav: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  navBrand: {
    ...typography.titleMd,
    color: colors.primaryPressed,
  },
  navActions: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  homeContent: {
    alignSelf: 'center',
    gap: spacing.lg,
    maxWidth: 430,
    padding: spacing.screen,
    paddingBottom: spacing.xxl,
    width: '100%',
  },
  homeHeader: {
    gap: spacing.sm,
    paddingTop: spacing.sm,
  },
  screenTitle: {
    ...typography.headlineLg,
    color: colors.onSurface,
  },
  screenSubtitle: {
    ...typography.bodySm,
    color: colors.onMuted,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
  },
  reelSkeletonTile: {
    aspectRatio: 0.72,
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderRadius: radius.lg,
    borderWidth: 1,
  },
  loadingSources: {
    gap: spacing.md,
  },
  loadingSourcesTitle: {
    ...typography.labelLg,
    color: colors.onSurface,
  },
  loadingSourcesBody: {
    ...typography.bodySm,
    color: colors.onMuted,
  },
  pendingSourcePrompt: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.md,
    borderWidth: 1,
    gap: spacing.md,
    padding: spacing.md,
  },
  pendingSourceCopy: {
    gap: spacing.xs,
  },
  pendingSourceTitle: {
    ...typography.labelLg,
    color: colors.onSurface,
  },
  pendingSourceUrl: {
    ...typography.bodySm,
    color: colors.onMuted,
  },
  pendingSourceActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
});
