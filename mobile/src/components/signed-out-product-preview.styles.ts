import { StyleSheet } from 'react-native';

import { colors, radius, spacing } from '@/theme';

export const styles = StyleSheet.create({
  authProductPreview: {
    alignItems: 'center',
    alignSelf: 'center',
    height: 336,
    justifyContent: 'center',
    maxWidth: 352,
    overflow: 'visible',
    position: 'relative',
    width: '100%',
  },
  authProductPreviewCompact: {
    height: 296,
    maxWidth: 278,
  },
  authPreviewReelShell: {
    aspectRatio: 0.56,
    backgroundColor: colors.ink,
    borderColor: 'rgba(16, 26, 23, 0.20)',
    borderRadius: radius.lg,
    borderWidth: 1,
    boxShadow: '0 16px 30px rgba(16, 26, 23, 0.18)',
    overflow: 'hidden',
    width: 142,
    zIndex: 3,
  },
  authPreviewReelShellCompact: {
    borderRadius: radius.md,
    width: 116,
  },
  authPreviewReelImage: {
    height: '100%',
    width: '100%',
  },
  authPreviewReelMeta: {
    alignItems: 'center',
    bottom: spacing.sm,
    flexDirection: 'row',
    gap: spacing.xs,
    left: spacing.sm,
    position: 'absolute',
  },
  authPreviewReelPlay: {
    color: colors.onPrimary,
    fontSize: 14,
    fontWeight: '700',
    lineHeight: 16,
  },
  authPreviewReelCount: {
    color: colors.onPrimary,
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 0,
    lineHeight: 16,
  },
  authOrbitGuide: {
    borderColor: 'rgba(14, 111, 104, 0.22)',
    borderRadius: 999,
    borderWidth: 1,
    position: 'absolute',
  },
  authOrbitGuideOuter: {
    height: 212,
    transform: [{ rotate: '-10deg' }],
    width: 336,
  },
  authOrbitGuideOuterCompact: {
    height: 176,
    width: 262,
  },
  authOrbitGuideInner: {
    height: 176,
    opacity: 0.6,
    transform: [{ rotate: '14deg' }],
    width: 282,
  },
  authOrbitGuideInnerCompact: {
    height: 146,
    width: 218,
  },
  authOrbitBook: {
    position: 'absolute',
    zIndex: 4,
  },
  authOrbitBookUpperLeft: {
    left: 12,
    top: 24,
  },
  authOrbitBookUpperLeftCompact: {
    left: 4,
    top: 22,
  },
  authOrbitBookUpperRight: {
    right: 12,
    top: 42,
  },
  authOrbitBookUpperRightCompact: {
    right: 4,
    top: 38,
  },
  authOrbitBookLowerLeft: {
    bottom: 18,
    left: 12,
  },
  authOrbitBookLowerLeftCompact: {
    bottom: 18,
    left: 4,
  },
  authOrbitBookLowerRight: {
    bottom: 22,
    right: 12,
  },
  authOrbitBookLowerRightCompact: {
    bottom: 20,
    right: 4,
  },
  authOrbitBookCover: {
    backgroundColor: colors.surfaceMuted,
    borderColor: 'rgba(16, 26, 23, 0.12)',
    borderRadius: radius.sm,
    borderWidth: 1,
    boxShadow: '0 9px 18px rgba(16, 26, 23, 0.14)',
    height: 94,
    overflow: 'hidden',
    width: 66,
  },
  authOrbitBookImage: {
    height: '100%',
    width: '100%',
  },
});
