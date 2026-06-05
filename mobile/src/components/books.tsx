import { Image, Text, View } from 'react-native';

import type { BookMention } from '@/captures';
import { MoreIcon } from '@/components/icons';
import { FadeInView } from '@/components/motion';
import { SourceToBooksPreview } from '@/components/product-preview';
import { BookSpine, BookSpineSkeleton, IconButton, PrimaryButton, SecondaryButton } from '@/components/ui';
import { styles } from '@/styles';

type BooksMentionedProps = {
  books: BookMention[];
  removingBookId?: string | null;
  onOpenRemoveBook?: (book: BookMention) => void;
};

type BookRowProps = {
  book: BookMention;
  isRemoving: boolean;
  showDivider: boolean;
  onOpenRemoveBook?: (book: BookMention) => void;
};

export function ProcessingBooks() {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Finding books...</Text>
      <Text style={styles.sectionSubtitle}>Mentioned is checking the saved source for book mentions.</Text>
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
      <BookSpineSkeleton />
      <View style={styles.skeletonTextGroup}>
        <View style={[styles.skeletonLine, { width: '78%' }]} />
        <View style={[styles.skeletonLine, { width: '52%' }]} />
        <View style={[styles.skeletonLine, { width: '92%' }]} />
      </View>
    </View>
  );
}

export function BooksMentioned({
  books,
  removingBookId = null,
  onOpenRemoveBook,
}: BooksMentionedProps) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Books mentioned</Text>
      <View style={styles.bookListSurface}>
        {books.map((book, index) => (
          <FadeInView key={book.id} delay={Math.min(index * 55, 220)}>
            <BookRow
              book={book}
              isRemoving={removingBookId === book.id}
              showDivider={index < books.length - 1}
              onOpenRemoveBook={onOpenRemoveBook}
            />
          </FadeInView>
        ))}
      </View>
    </View>
  );
}

function BookRow({ book, isRemoving, showDivider, onOpenRemoveBook }: BookRowProps) {
  return (
    <View>
      <View style={styles.bookRow}>
        {book.coverImageUrl ? (
          <Image
            source={{ uri: book.coverImageUrl }}
            resizeMode="cover"
            style={styles.bookCoverImage}
          />
        ) : (
          <BookSpine color={book.color} initials={book.initials} />
        )}
        <View style={styles.bookCopy}>
          <Text style={styles.bookTitle}>{book.title}</Text>
          {book.author ? <Text style={styles.bookAuthor}>{book.author}</Text> : null}
          {book.synopsis ? <Text style={styles.bookSynopsis}>{book.synopsis}</Text> : null}
        </View>
        {onOpenRemoveBook ? (
          <View style={styles.bookRowAction}>
            <IconButton
              accessibilityLabel={`Remove ${book.title}`}
              disabled={isRemoving}
              onPress={() => onOpenRemoveBook(book)}
            >
              <MoreIcon />
            </IconButton>
          </View>
        ) : null}
      </View>
      {showDivider ? <View style={styles.bookRowDivider} /> : null}
    </View>
  );
}

export function NoBooks({ onOpenSource }: { onOpenSource: () => void }) {
  return (
    <View style={styles.stateCard}>
      <Text style={styles.stateTitle}>No books found in this source</Text>
      <Text style={styles.stateBody}>
        The source is still saved. Mentioned did not find a clear book mention to show here.
      </Text>
      <View style={styles.statePreviewWrap}>
        <SourceToBooksPreview />
      </View>
      <View style={styles.stateActions}>
        <SecondaryButton label="Open on Instagram" onPress={onOpenSource} compact />
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
      <Text style={styles.stateTitle}>Could not find books from this source</Text>
      <Text style={styles.stateBody}>
        The source is still saved. Try again, or open the original source.
      </Text>
      <View style={styles.stateActions}>
        <PrimaryButton
          label={isRetrying ? 'Retrying...' : 'Retry'}
          onPress={onRetry}
          compact
          disabled={isRetrying}
        />
        <SecondaryButton label="Open on Instagram" onPress={onOpenSource} compact />
      </View>
    </View>
  );
}
