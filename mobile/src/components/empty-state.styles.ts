import { StyleSheet } from 'react-native';

import { colors, spacing, typography } from '@/theme';

export const styles = StyleSheet.create({
  emptyScene: {
    alignItems: 'center',
    gap: spacing.md,
    marginTop: spacing.xxl,
    paddingHorizontal: spacing.lg,
  },
  emptySceneTitle: {
    ...typography.titleLg,
    color: colors.onSurface,
    marginTop: spacing.sm,
    textAlign: 'center',
  },
  emptySceneBody: {
    ...typography.bodySm,
    color: colors.onMuted,
    maxWidth: 280,
    textAlign: 'center',
  },
  emptySceneActions: {
    marginTop: spacing.sm,
  },
});
