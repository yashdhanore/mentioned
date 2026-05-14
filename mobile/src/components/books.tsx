import { Text, View } from 'react-native';

import type { BookMention } from '@/captures';
import { PrimaryButton, SecondaryButton } from '@/components/ui';
import { styles } from '@/styles';

export function ProcessingBooks() {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Finding books...</Text>
      <View style={styles.skeletonList}>
        <SkeletonBookRow />
        <SkeletonBookRow />
      </View>
    </View>
  );
}

function SkeletonBookRow() {
  return (
    <View style={styles.bookRow}>
      <View style={styles.skeletonCover} />
      <View style={styles.skeletonTextGroup}>
        <View style={[styles.skeletonLine, { width: '78%' }]} />
        <View style={[styles.skeletonLine, { width: '52%' }]} />
        <View style={[styles.skeletonLine, { width: '92%' }]} />
      </View>
    </View>
  );
}

export function BooksMentioned({ books }: { books: BookMention[] }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Books mentioned</Text>
      <View style={styles.bookList}>
        {books.map((book) => (
          <BookRow key={book.id} book={book} />
        ))}
      </View>
    </View>
  );
}

function BookRow({ book }: { book: BookMention }) {
  return (
    <View style={styles.bookRow}>
      <View style={[styles.bookCover, { backgroundColor: book.color }]}>
        <Text style={styles.bookCoverText}>{book.initials}</Text>
      </View>
      <View style={styles.bookCopy}>
        <Text style={styles.bookTitle}>{book.title}</Text>
        {book.author ? <Text style={styles.bookAuthor}>{book.author}</Text> : null}
        {book.synopsis ? <Text style={styles.bookSynopsis}>{book.synopsis}</Text> : null}
      </View>
    </View>
  );
}

export function NoBooks({ onOpenSource }: { onOpenSource: () => void }) {
  return (
    <View style={styles.stateCard}>
      <Text style={styles.stateTitle}>No books found in this Reel</Text>
      <Text style={styles.stateBody}>
        We saved the Reel, but did not find a useful book mention to show here.
      </Text>
      <View style={styles.stateActions}>
        <SecondaryButton label="Open source" onPress={onOpenSource} compact />
      </View>
    </View>
  );
}

export function FailedState({
  isRetrying,
  onOpenSource,
  onRetry,
}: {
  isRetrying: boolean;
  onOpenSource: () => void;
  onRetry: () => void;
}) {
  return (
    <View style={styles.stateCard}>
      <Text style={styles.stateTitle}>Could not find books from this Reel</Text>
      <Text style={styles.stateBody}>
        The source is still saved. Try again, or open the original Reel.
      </Text>
      <View style={styles.stateActions}>
        <PrimaryButton
          label={isRetrying ? 'Retrying...' : 'Retry'}
          onPress={onRetry}
          compact
          disabled={isRetrying}
        />
        <SecondaryButton label="Open source" onPress={onOpenSource} compact />
      </View>
    </View>
  );
}
