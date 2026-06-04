import {
  close,
  openHostApp,
  type InitialProps,
  Text,
  View,
} from 'expo-share-extension';
import { Pressable, StyleSheet } from 'react-native';

import { extractSharedSourceUrl } from './src/utils/shared-source-url';

export default function ShareExtension(props: InitialProps) {
  const sourceUrl = extractSharedSourceUrl({ url: props.url, text: props.text });

  const openMentioned = () => {
    if (!sourceUrl) {
      close();
      return;
    }

    openHostApp(`share?url=${sourceUrl}`);
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{sourceUrl ? 'Save to Mentioned' : 'Unsupported source'}</Text>
      <Text style={styles.body}>
        {sourceUrl ? 'Open Mentioned to save this source.' : 'Share an Instagram Reel or post link.'}
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
    color: '#101A17',
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
    color: '#101A17',
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
    backgroundColor: '#101A17',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 16,
  },
  primaryButtonText: {
    color: '#FFFFFF',
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
    color: '#101A17',
    fontSize: 15,
    fontWeight: '600',
  },
});
