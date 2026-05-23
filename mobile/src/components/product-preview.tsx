import { Text, View } from 'react-native';

import { BookSpine, Surface } from '@/components/ui';
import { styles } from '@/styles';

const previewBooks = [
  { title: 'The Shallows', author: 'Nicholas Carr', initials: 'TS', color: '#405B55' },
  { title: 'Deep Work', author: 'Cal Newport', initials: 'DW', color: '#2F4A44' },
];

export function SourceToBooksPreview() {
  return (
    <View style={styles.productPreview}>
      <View style={styles.previewReelCard}>
        <View style={styles.previewImageWash} />
        <View style={styles.previewScrim} />
        <Text style={styles.previewReelText}>This book changed how I think about attention.</Text>
        <Text style={styles.previewCreator}>@source</Text>
      </View>

      <View style={styles.previewConnector}>
        <View style={styles.previewConnectorDot} />
        <View style={styles.previewConnectorLine} />
        <View style={styles.previewConnectorDot} />
      </View>

      <View style={styles.previewBookStack}>
        <Text style={styles.previewBookLabel}>Books mentioned</Text>
        {previewBooks.map((book) => (
          <Surface key={book.title} style={styles.previewBookRow}>
            <BookSpine color={book.color} initials={book.initials} title={book.title} />
            <View style={styles.previewBookCopy}>
              <Text numberOfLines={1} style={styles.previewBookTitle}>
                {book.title}
              </Text>
              <Text numberOfLines={1} style={styles.previewBookAuthor}>
                {book.author}
              </Text>
            </View>
          </Surface>
        ))}
      </View>
    </View>
  );
}
