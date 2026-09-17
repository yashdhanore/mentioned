import { useEffect, useState } from 'react';
import { Image, Linking, Pressable, Text, View } from 'react-native';

import type { Mention, MentionCategory } from '@/captures';
import { mapsUrlForMention } from '@/captures';
import { PlaceIcon, ProductIcon } from '@/components/icons';
import { FadeInView } from '@/components/motion';
import { SourceToBooksPreview } from '@/components/product-preview';
import { BookSpine, BookSpineSkeleton, PrimaryButton, SecondaryButton } from '@/components/ui';
import { styles as sharedStyles } from '@/styles';
import { styles as localStyles } from './mentions.styles';

const styles = { ...sharedStyles, ...localStyles };

type MentionsListProps = {
  mentions: Mention[];
};

type MentionRowProps = {
  mention: Mention;
  showDivider: boolean;
};

const SECTION_TITLE: Record<MentionCategory, string> = {
  book: 'Books mentioned',
  place: 'Places mentioned',
  product: 'Products mentioned',
};

function sectionTitleFor(mentions: Mention[]): string {
  // Posts are single-type; the first item determines the header.
  return mentions.length > 0 ? SECTION_TITLE[mentions[0].category] : 'Mentions';
}

export function ProcessingMentions() {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Finding mentions...</Text>
      <Text style={styles.sectionSubtitle}>
        Mentioned is checking this post for books, places, and products.
      </Text>
      <View style={styles.skeletonList}>
        <SkeletonMentionRow />
        <SkeletonMentionRow />
      </View>
    </View>
  );
}

function SkeletonMentionRow() {
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

export function MentionsList({ mentions }: MentionsListProps) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{sectionTitleFor(mentions)}</Text>
      <View style={styles.bookListSurface}>
        {mentions.map((mention, index) => (
          <FadeInView key={mention.id} delay={Math.min(index * 55, 220)}>
            <MentionRow mention={mention} showDivider={index < mentions.length - 1} />
          </FadeInView>
        ))}
      </View>
    </View>
  );
}

function MentionTile({ mention }: { mention: Mention }) {
  if (mention.category === 'place') {
    return (
      <View style={[styles.bookSpine, { backgroundColor: mention.color }]}>
        <PlaceIcon color="#FFFFFF" size={22} />
      </View>
    );
  }
  if (mention.category === 'product') {
    return (
      <View style={[styles.bookSpine, { backgroundColor: mention.color }]}>
        <ProductIcon color="#FFFFFF" size={22} />
      </View>
    );
  }
  return <BookSpine color={mention.color} initials={mention.initials} />;
}

function MentionRow({ mention, showDivider }: MentionRowProps) {
  const [didFailCoverLoad, setDidFailCoverLoad] = useState(false);
  const shouldShowCoverImage = Boolean(mention.coverImageUrl) && !didFailCoverLoad;

  useEffect(() => {
    setDidFailCoverLoad(false);
  }, [mention.coverImageUrl]);

  const mapsUrl = mapsUrlForMention(mention);

  const rowContent = (
    <View style={styles.bookRow}>
      {shouldShowCoverImage && mention.coverImageUrl ? (
        <Image
          source={{ uri: mention.coverImageUrl }}
          resizeMode="cover"
          style={styles.bookCoverImage}
          onError={() => setDidFailCoverLoad(true)}
        />
      ) : (
        <MentionTile mention={mention} />
      )}
      <View style={styles.bookCopy}>
        <Text style={styles.bookTitle}>{mention.title}</Text>
        {mention.subtitle ? <Text style={styles.bookAuthor}>{mention.subtitle}</Text> : null}
      </View>
    </View>
  );

  return (
    <View>
      {mapsUrl ? (
        <Pressable
          accessibilityRole="link"
          onPress={() => void Linking.openURL(mapsUrl)}
        >
          {rowContent}
        </Pressable>
      ) : (
        rowContent
      )}
      {showDivider ? <View style={styles.bookRowDivider} /> : null}
    </View>
  );
}

export function NoMentions({
  onOpenSource,
  wasSkipped = false,
}: {
  onOpenSource: () => void;
  wasSkipped?: boolean;
}) {
  return (
    <View style={styles.stateCard}>
      <Text style={styles.stateTitle}>
        {wasSkipped ? 'Nothing to extract from this post' : 'Nothing found in this post'}
      </Text>
      <Text style={styles.stateBody}>
        {wasSkipped
          ? "The post is still saved. This one doesn't look like it features any books, places, or products."
          : "The post is still saved. Mentioned didn't find a clear book, place, or product to show here."}
      </Text>
      <View style={styles.statePreviewWrap}>
        <SourceToBooksPreview />
      </View>
      <View style={styles.stateActions}>
        <SecondaryButton label="Open original" onPress={onOpenSource} compact />
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
      <Text style={styles.stateTitle}>Could not find mentions in this post</Text>
      <Text style={styles.stateBody}>
        The post is still saved. Try again, or open the original.
      </Text>
      <View style={styles.stateActions}>
        <PrimaryButton
          label={isRetrying ? 'Retrying...' : 'Retry'}
          onPress={onRetry}
          compact
          disabled={isRetrying}
        />
        <SecondaryButton label="Open original" onPress={onOpenSource} compact />
      </View>
    </View>
  );
}
