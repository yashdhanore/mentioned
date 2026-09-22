import {
  close,
  openHostApp,
  type InitialProps,
  Text,
  View,
} from 'expo-share-extension';
import { useEffect, useRef } from 'react';
import { Pressable, StyleSheet } from 'react-native';

import { colors } from './src/theme';
import { extractSharedSourceUrl } from './src/utils/shared-source-url';

export default function ShareExtension(props: InitialProps) {
  const sourceUrl = extractSharedSourceUrl({ url: props.url, text: props.text });

  const openMentioned = () => {
    if (!sourceUrl) {
      close();
      return;
    }

    openHostApp(`share?url=${encodeURIComponent(sourceUrl)}`);
  };

  // Hand off to the app automatically so the user doesn't have to tap through
  // the extension. The button below stays as a fallback if the automatic
  // handoff is interrupted. Guarded so it fires at most once.
  const handedOffRef = useRef(false);
  useEffect(() => {
    if (sourceUrl && !handedOffRef.current) {
      handedOffRef.current = true;
      openHostApp(`share?url=${encodeURIComponent(sourceUrl)}`);
    }
  }, [sourceUrl]);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{sourceUrl ? 'Opening Mentioned…' : 'Unsupported source'}</Text>
      <Text style={styles.body}>
        {sourceUrl ? 'Saving this source. Tap below if it doesn’t open.' : 'Share an Instagram Reel or post link.'}
      </Text>
      {sourceUrl ? (
        <Text ellipsizeMode="middle" numberOfLines={2} style={styles.url}>
          {sourceUrl}
        </Text>
      ) : null}
      <View style={styles.actions}>
        {sourceUrl ? (
          <Pressable accessibilityRole="button" onPress={openMentioned} style={styles.primaryButton}>
            <Text style={styles.primaryButtonText}>Open Mentioned</Text>
          </Pressable>
        ) : null}
        <Pressable accessibilityRole="button" onPress={close} style={styles.secondaryButton}>
          <Text style={styles.secondaryButtonText}>{sourceUrl ? 'Cancel' : 'Close'}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F6F8F5',
    paddingHorizontal: 20,
    paddingVertical: 18,
    justifyContent: 'center',
  },
  title: {
    color: colors.ink,
    fontSize: 20,
    fontWeight: '700',
    marginBottom: 8,
    textAlign: 'center',
  },
  body: {
    color: '#51615B',
    fontSize: 15,
    lineHeight: 21,
    marginBottom: 10,
    textAlign: 'center',
  },
  url: {
    color: colors.ink,
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 16,
    textAlign: 'center',
  },
  actions: {
    gap: 10,
  },
  primaryButton: {
    minHeight: 48,
    borderRadius: 8,
    backgroundColor: colors.ink,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 16,
  },
  primaryButtonText: {
    color: colors.onPrimary,
    fontSize: 16,
    fontWeight: '700',
  },
  secondaryButton: {
    minHeight: 44,
    borderRadius: 8,
    borderColor: '#C9D3CE',
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 16,
  },
  secondaryButtonText: {
    color: colors.ink,
    fontSize: 15,
    fontWeight: '600',
  },
});
