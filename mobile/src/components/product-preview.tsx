import { Image, Text, View } from 'react-native';

import { styles } from '@/styles';

const previewBooks = [
  {
    title: 'The Shallows',
    author: 'Nicholas Carr',
    initials: 'TS',
    coverColor: '#E7DECC',
    textColor: '#27332F',
  },
  {
    title: 'Deep Work',
    author: 'Cal Newport',
    initials: 'DW',
    coverColor: '#202A28',
    textColor: '#F8F3EA',
  },
];

const previewReelImage = require('../../assets/preview-reel.png');

export function SourceToBooksPreview() {
  return (
    <View style={styles.productPreview}>
      <View style={styles.previewReelCard}>
        <Image source={previewReelImage} style={styles.previewReelImage} />
        <View style={styles.previewScrim} />
        <View style={styles.previewSourceMeta}>
          <Text numberOfLines={1} style={styles.previewCreator}>
            @annelewis
          </Text>
          <View style={styles.previewSourcePill}>
            <View style={styles.previewPlayGlyph} />
            <Text style={styles.previewDuration}>1.2M</Text>
          </View>
        </View>
      </View>

      <View style={styles.previewConnector}>
        <View style={styles.previewConnectorDot} />
        <View style={styles.previewConnectorLine} />
        <View style={styles.previewConnectorDot} />
      </View>

      <View style={styles.previewBookStack}>
        <Text style={styles.previewBookLabel}>Books mentioned</Text>
        {previewBooks.map((book, index) => (
          <View
            key={book.title}
            style={[
              styles.previewBookCard,
              index === 0 ? styles.previewBookCardFirst : styles.previewBookCardSecond,
            ]}
          >
            <View style={[styles.previewBookObject, { backgroundColor: book.coverColor }]}>
              <View style={styles.previewBookPageEdge} />
              <Text style={[styles.previewBookObjectText, { color: book.textColor }]}>{book.initials}</Text>
            </View>
            <View style={styles.previewBookCardCopy}>
              <Text numberOfLines={1} style={styles.previewBookTitle}>
                {book.title}
              </Text>
              <Text numberOfLines={1} style={styles.previewBookAuthor}>
                {book.author}
              </Text>
            </View>
          </View>
        ))}
      </View>
    </View>
  );
}
