import { StyleSheet } from 'react-native';

import { colors, radius, spacing } from '@/theme';

export const styles = StyleSheet.create({
  authProviderGroup: {
    gap: spacing.md,
    width: '100%',
    alignItems: 'center',
  },
  authProviderGroupBusy: {
    opacity: 0.5,
  },
  authProviderOverlay: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
  },
  authWebButton: {
    alignItems: 'center',
    borderRadius: radius.md,
    flexDirection: 'row',
    overflow: 'hidden',
    position: 'relative',
    height: 52,
    justifyContent: 'center',
    paddingHorizontal: spacing.xl,
    width: 312,
  },
  authWebButtonApple: {
    backgroundColor: '#000000',
    borderColor: '#111111',
    borderWidth: 1,
  },
  authWebButtonGoogle: {
    backgroundColor: '#151B1F',
    borderColor: 'rgba(255, 255, 255, 0.16)',
    borderWidth: 1,
  },
  authWebButtonText: {
    color: colors.onPrimary,
    fontSize: 17,
    fontWeight: '500',
    letterSpacing: 0,
    lineHeight: 22,
  },
  authWebAppleContent: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.md,
    justifyContent: 'center',
  },
  authWebAppleGlyph: {
    color: colors.onPrimary,
    fontSize: 25,
    fontWeight: '600',
    lineHeight: 28,
  },
  authWebGoogleIconWell: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRightColor: 'rgba(16, 26, 23, 0.16)',
    borderRightWidth: 1,
    borderBottomLeftRadius: radius.md - 1,
    borderTopLeftRadius: radius.md - 1,
    bottom: 1,
    justifyContent: 'center',
    left: 1,
    position: 'absolute',
    top: 1,
    width: 50,
  },
});
