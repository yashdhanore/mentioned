import { StyleSheet } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';

export const styles = StyleSheet.create({
  section: {
    gap: spacing.md,
    marginTop: spacing.lg,
  },
  sectionTitle: {
    ...typography.headlineMd,
    color: colors.onSurface,
  },
  sectionSubtitle: {
    ...typography.bodySm,
    color: colors.onMuted,
  },
  bookListSurface: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.md,
    borderWidth: 1,
    overflow: 'hidden',
  },
  bookRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.md,
    minHeight: 112,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  bookRowDivider: {
    backgroundColor: colors.border,
    height: 1,
    marginLeft: spacing.md + 52 + spacing.md,
  },
  bookCoverImage: {
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.hairline,
    borderRadius: radius.sm,
    borderWidth: 1,
    height: 74,
    width: 52,
  },
  bookCopy: {
    flex: 1,
    gap: spacing.xs,
    minWidth: 0,
  },
  bookTitle: {
    ...typography.titleMd,
    color: colors.onSurface,
  },
  bookAuthor: {
    ...typography.bodySm,
    color: colors.secondary,
  },
  skeletonList: {
    gap: spacing.md,
  },
  skeletonTextGroup: {
    flex: 1,
    gap: spacing.sm,
  },
  skeletonLine: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.xs,
    height: 10,
  },
  stateCard: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.md,
    borderWidth: 1,
    gap: spacing.md,
    marginTop: spacing.lg,
    padding: spacing.lg,
  },
  stateTitle: {
    ...typography.titleLg,
    color: colors.onSurface,
  },
  stateBody: {
    ...typography.bodySm,
    color: colors.onMuted,
  },
  stateActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  statePreviewWrap: {
    alignItems: 'center',
    overflow: 'hidden',
  },
});
