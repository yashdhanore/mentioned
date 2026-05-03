import { StatusBar } from 'expo-status-bar';
import { useMemo, useState } from 'react';
import {
  Image,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from 'react-native';

import { books, savedReels, type Book, type SavedReel } from './src/mockData';
import { colors, radius, spacing, typography } from './src/theme';

type Sheet = 'profile' | 'paste' | 'reelMenu' | null;

export default function App() {
  const { width } = useWindowDimensions();
  const [isSignedIn, setIsSignedIn] = useState(false);
  const [selectedReel, setSelectedReel] = useState<SavedReel | null>(null);
  const [sheet, setSheet] = useState<Sheet>(null);
  const [pasteUrl, setPasteUrl] = useState('');

  const tileWidth = useMemo(() => {
    return (width - spacing.screen * 2 - spacing.md) / 2;
  }, [width]);

  function showProcessingFromPaste() {
    const processing = savedReels.find((reel) => reel.status === 'processing') ?? savedReels[0];
    setPasteUrl('');
    setSheet(null);
    setSelectedReel(processing);
  }

  if (!isSignedIn) {
    return <SignedOutScreen onContinue={() => setIsSignedIn(true)} />;
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      {selectedReel ? (
        <ReelDetail
          reel={selectedReel}
          width={width}
          onBack={() => setSelectedReel(null)}
          onOpenMenu={() => setSheet('reelMenu')}
        />
      ) : (
        <HomeScreen
          tileWidth={tileWidth}
          onOpenPaste={() => setSheet('paste')}
          onOpenProfile={() => setSheet('profile')}
          onOpenReel={setSelectedReel}
        />
      )}

      <ProfileSheet visible={sheet === 'profile'} onClose={() => setSheet(null)} />
      <PasteSheet
        visible={sheet === 'paste'}
        value={pasteUrl}
        onChange={setPasteUrl}
        onClose={() => setSheet(null)}
        onSubmit={showProcessingFromPaste}
      />
      <ReelMenuSheet visible={sheet === 'reelMenu'} onClose={() => setSheet(null)} />
    </SafeAreaView>
  );
}

function SignedOutScreen({ onContinue }: { onContinue: () => void }) {
  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <View style={styles.authScreen}>
        <View style={styles.authMark}>
          <Text style={styles.authMarkText}>M</Text>
        </View>
        <View style={styles.authCopy}>
          <Text style={styles.authBrand}>Mentioned</Text>
          <Text style={styles.authTitle}>Save Reels and see the books mentioned inside them.</Text>
          <Text style={styles.authBody}>
            Share a Reel to Mentioned. We keep the source with the books it mentions, so you can find
            them later.
          </Text>
        </View>
        <View style={styles.authActions}>
          <PrimaryButton label="Continue with Apple" onPress={onContinue} />
          <SecondaryButton label="Continue with Google" onPress={onContinue} />
        </View>
      </View>
    </SafeAreaView>
  );
}

function HomeScreen({
  tileWidth,
  onOpenPaste,
  onOpenProfile,
  onOpenReel,
}: {
  tileWidth: number;
  onOpenPaste: () => void;
  onOpenProfile: () => void;
  onOpenReel: (reel: SavedReel) => void;
}) {
  return (
    <ScrollView
      contentContainerStyle={styles.homeContent}
      showsVerticalScrollIndicator={false}
      bounces
    >
      <View style={styles.topNav}>
        <Text style={styles.navBrand}>Mentioned</Text>
        <View style={styles.navActions}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Paste link"
            style={({ pressed }) => [styles.navSquareButton, pressed && styles.pressed]}
            onPress={onOpenPaste}
          >
            <Text style={styles.navButtonText}>+</Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Open profile and settings"
            style={({ pressed }) => [styles.profileButton, pressed && styles.pressed]}
            onPress={onOpenProfile}
          >
            <Text style={styles.profileButtonText}>Y</Text>
          </Pressable>
        </View>
      </View>

      <View style={styles.homeHeader}>
        <Text style={styles.screenTitle}>Saved Reels</Text>
        <Text style={styles.screenSubtitle}>Shared sources you want to return to.</Text>
      </View>

      <View style={styles.grid}>
        {savedReels.map((reel) => (
          <ReelTile
            key={reel.id}
            reel={reel}
            width={tileWidth}
            onPress={() => onOpenReel(reel)}
          />
        ))}
      </View>
    </ScrollView>
  );
}

function ReelTile({ reel, width, onPress }: { reel: SavedReel; width: number; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${reel.creator} saved Reel`}
      style={({ pressed }) => [styles.reelTile, { width }, pressed && styles.pressed]}
      onPress={onPress}
    >
      <Image source={{ uri: reel.thumbnailUrl }} style={styles.reelTileImage} />
      <View style={styles.reelTileScrim} />
      {reel.status !== 'ready' ? <TileStatus status={reel.status} /> : null}
      <Text numberOfLines={1} style={styles.reelCreator}>
        {reel.creator}
      </Text>
    </Pressable>
  );
}

function TileStatus({ status }: { status: SavedReel['status'] }) {
  if (status === 'processing') {
    return <View accessibilityLabel="Processing" style={styles.processingDot} />;
  }

  return (
    <View accessibilityLabel="Needs attention" style={styles.attentionDot}>
      <Text style={styles.attentionText}>!</Text>
    </View>
  );
}

function ReelDetail({
  reel,
  width,
  onBack,
  onOpenMenu,
}: {
  reel: SavedReel;
  width: number;
  onBack: () => void;
  onOpenMenu: () => void;
}) {
  const previewWidth = Math.min(width * 0.74, 318);

  return (
    <ScrollView
      contentContainerStyle={styles.detailContent}
      showsVerticalScrollIndicator={false}
      bounces
    >
      <View style={styles.detailNav}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Back to saved Reels"
          style={({ pressed }) => [styles.backButton, pressed && styles.pressed]}
          onPress={onBack}
        >
          <Text style={styles.backText}>Back</Text>
        </Pressable>
        <Text numberOfLines={1} style={styles.detailNavTitle}>
          {reel.creator}
        </Text>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Open Reel actions"
          style={({ pressed }) => [styles.navSquareButton, pressed && styles.pressed]}
          onPress={onOpenMenu}
        >
          <Text style={styles.navButtonText}>...</Text>
        </Pressable>
      </View>

      <View style={styles.previewWrap}>
        <View style={[styles.reelPreview, { width: previewWidth }]}>
          <Image source={{ uri: reel.thumbnailUrl }} style={styles.reelPreviewImage} />
        </View>
      </View>

      <View style={styles.sourceBlock}>
        <Text style={styles.sourceCreator}>{reel.creator}</Text>
        {reel.sourceContextSnippet ? (
          <Text numberOfLines={2} style={styles.sourceSnippet}>
            {reel.sourceContextSnippet}
          </Text>
        ) : null}
      </View>

      {reel.status === 'processing' ? <ProcessingBooks /> : null}
      {reel.status === 'ready' ? <BooksMentioned books={reel.books} /> : null}
      {reel.status === 'no_books' ? <NoBooks /> : null}
      {reel.status === 'failed' ? <FailedState /> : null}
    </ScrollView>
  );
}

function ProcessingBooks() {
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

function BooksMentioned({ books: mentionedBooks }: { books: Book[] }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Books mentioned</Text>
      <View style={styles.bookList}>
        {mentionedBooks.map((book) => (
          <BookRow key={book.id} book={book} />
        ))}
      </View>
    </View>
  );
}

function BookRow({ book }: { book: Book }) {
  return (
    <View style={styles.bookRow}>
      <View style={[styles.bookCover, { backgroundColor: book.color }]}>
        <Text style={styles.bookCoverText}>{book.initials}</Text>
      </View>
      <View style={styles.bookCopy}>
        <Text style={styles.bookTitle}>{book.title}</Text>
        <Text style={styles.bookAuthor}>{book.author}</Text>
        <Text style={styles.bookSynopsis}>{book.synopsis}</Text>
      </View>
    </View>
  );
}

function NoBooks() {
  return (
    <View style={styles.stateCard}>
      <Text style={styles.stateTitle}>No books found in this Reel</Text>
      <Text style={styles.stateBody}>
        We saved the Reel, but did not find a useful book mention to show here.
      </Text>
      <View style={styles.stateActions}>
        <SecondaryButton label="Open source" onPress={() => undefined} compact />
        <SecondaryButton label="Remove from saved" onPress={() => undefined} compact />
      </View>
    </View>
  );
}

function FailedState() {
  return (
    <View style={styles.stateCard}>
      <Text style={styles.stateTitle}>Could not find books from this Reel</Text>
      <Text style={styles.stateBody}>
        The source is still saved. Try again, or open the original Reel.
      </Text>
      <View style={styles.stateActions}>
        <PrimaryButton label="Retry" onPress={() => undefined} compact />
        <SecondaryButton label="Open source" onPress={() => undefined} compact />
      </View>
    </View>
  );
}

function ProfileSheet({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  return (
    <BottomSheet visible={visible} onClose={onClose}>
      <Text style={styles.sheetTitle}>Profile</Text>
      <Text style={styles.accountEmail}>ydh0rs@example.com</Text>
      <View style={styles.sheetMenu}>
        <SheetRow label="How sharing works" />
        <SheetRow label="Privacy" />
        <SheetRow label="Sign out" />
        <SheetRow label="Delete account" destructive />
      </View>
    </BottomSheet>
  );
}

function PasteSheet({
  visible,
  value,
  onChange,
  onClose,
  onSubmit,
}: {
  visible: boolean;
  value: string;
  onChange: (value: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  return (
    <BottomSheet visible={visible} onClose={onClose}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <Text style={styles.sheetTitle}>Paste link</Text>
        <Text style={styles.sheetBody}>Use this when sharing from the source app is not available.</Text>
        <Text style={styles.inputLabel}>Reel URL</Text>
        <TextInput
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
          onChangeText={onChange}
          placeholder="https://www.instagram.com/reel/..."
          placeholderTextColor={colors.onMuted}
          style={styles.input}
          value={value}
        />
        <PrimaryButton label="Find books" onPress={onSubmit} />
      </KeyboardAvoidingView>
    </BottomSheet>
  );
}

function ReelMenuSheet({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  return (
    <BottomSheet visible={visible} onClose={onClose}>
      <Text style={styles.sheetTitle}>Reel actions</Text>
      <View style={styles.sheetMenu}>
        <SheetRow label="Open source" />
        <SheetRow label="Remove from saved" destructive />
      </View>
    </BottomSheet>
  );
}

function BottomSheet({
  visible,
  onClose,
  children,
}: {
  visible: boolean;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <Modal animationType="slide" transparent visible={visible} onRequestClose={onClose}>
      <Pressable style={styles.modalOverlay} onPress={onClose}>
        <Pressable style={styles.bottomSheet}>
          <View style={styles.sheetHandle} />
          {children}
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function SheetRow({ label, destructive = false }: { label: string; destructive?: boolean }) {
  return (
    <Pressable style={({ pressed }) => [styles.sheetRow, pressed && styles.pressed]}>
      <Text style={[styles.sheetRowText, destructive && styles.destructiveText]}>{label}</Text>
    </Pressable>
  );
}

function PrimaryButton({
  label,
  onPress,
  compact = false,
}: {
  label: string;
  onPress: () => void;
  compact?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      style={({ pressed }) => [
        styles.primaryButton,
        compact && styles.compactButton,
        pressed && styles.pressed,
      ]}
      onPress={onPress}
    >
      <Text style={styles.primaryButtonText}>{label}</Text>
    </Pressable>
  );
}

function SecondaryButton({
  label,
  onPress,
  compact = false,
}: {
  label: string;
  onPress: () => void;
  compact?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      style={({ pressed }) => [
        styles.secondaryButton,
        compact && styles.compactButton,
        pressed && styles.pressed,
      ]}
      onPress={onPress}
    >
      <Text style={styles.secondaryButtonText}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.neutral,
  },
  pressed: {
    transform: [{ scale: 0.98 }],
    opacity: 0.88,
  },
  authScreen: {
    flex: 1,
    justifyContent: 'space-between',
    padding: spacing.screen,
    paddingTop: spacing.xxl + spacing.xl,
    paddingBottom: spacing.xxl,
  },
  authMark: {
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.md,
    borderWidth: 1,
    height: 42,
    justifyContent: 'center',
    width: 42,
  },
  authMarkText: {
    ...typography.titleMd,
    color: colors.primary,
  },
  authCopy: {
    gap: spacing.md,
  },
  authBrand: {
    ...typography.labelLg,
    color: colors.secondary,
  },
  authTitle: {
    ...typography.headlineLg,
    color: colors.onSurface,
    maxWidth: 330,
  },
  authBody: {
    ...typography.bodyMd,
    color: colors.onMuted,
    maxWidth: 340,
  },
  authActions: {
    gap: spacing.md,
  },
  topNav: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  navBrand: {
    ...typography.labelLg,
    color: colors.secondary,
  },
  navActions: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  navSquareButton: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.md,
    borderWidth: 1,
    height: 38,
    justifyContent: 'center',
    width: 38,
  },
  navButtonText: {
    ...typography.labelLg,
    color: colors.onSurface,
  },
  profileButton: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderRadius: 19,
    height: 38,
    justifyContent: 'center',
    width: 38,
  },
  profileButtonText: {
    ...typography.labelLg,
    color: colors.onPrimary,
  },
  homeContent: {
    gap: spacing.xl,
    padding: spacing.screen,
    paddingBottom: spacing.xxl,
  },
  homeHeader: {
    gap: spacing.xs,
  },
  screenTitle: {
    ...typography.headlineLg,
    color: colors.onSurface,
  },
  screenSubtitle: {
    ...typography.bodySm,
    color: colors.onMuted,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
  },
  reelTile: {
    aspectRatio: 0.72,
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderRadius: radius.lg,
    borderWidth: 1,
    overflow: 'hidden',
  },
  reelTileImage: {
    height: '100%',
    width: '100%',
  },
  reelTileScrim: {
    backgroundColor: 'rgba(20, 32, 27, 0.22)',
    bottom: 0,
    height: 54,
    left: 0,
    position: 'absolute',
    right: 0,
  },
  reelCreator: {
    ...typography.caption,
    bottom: spacing.sm,
    color: colors.onPrimary,
    left: spacing.sm,
    position: 'absolute',
    right: spacing.sm,
  },
  processingDot: {
    backgroundColor: colors.warningSoft,
    borderColor: colors.warning,
    borderRadius: 9,
    borderWidth: 1,
    height: 18,
    position: 'absolute',
    right: spacing.sm,
    top: spacing.sm,
    width: 18,
  },
  attentionDot: {
    alignItems: 'center',
    backgroundColor: colors.errorSoft,
    borderColor: colors.error,
    borderRadius: 9,
    borderWidth: 1,
    height: 18,
    justifyContent: 'center',
    position: 'absolute',
    right: spacing.sm,
    top: spacing.sm,
    width: 18,
  },
  attentionText: {
    color: colors.error,
    fontSize: 11,
    fontWeight: '700',
    lineHeight: 13,
  },
  detailContent: {
    padding: spacing.screen,
    paddingBottom: spacing.xxl,
  },
  detailNav: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.md,
    justifyContent: 'space-between',
  },
  backButton: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.md,
    borderWidth: 1,
    height: 38,
    justifyContent: 'center',
    paddingHorizontal: spacing.md,
  },
  backText: {
    ...typography.labelMd,
    color: colors.onSurface,
  },
  detailNavTitle: {
    ...typography.labelLg,
    color: colors.secondary,
    flex: 1,
    textAlign: 'center',
  },
  previewWrap: {
    alignItems: 'center',
    marginTop: spacing.xl,
  },
  reelPreview: {
    aspectRatio: 9 / 16,
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderRadius: radius.lg,
    borderWidth: 1,
    overflow: 'hidden',
  },
  reelPreviewImage: {
    height: '100%',
    width: '100%',
  },
  sourceBlock: {
    alignItems: 'center',
    gap: spacing.xs,
    marginTop: spacing.lg,
    paddingHorizontal: spacing.md,
  },
  sourceCreator: {
    ...typography.labelLg,
    color: colors.onSurface,
  },
  sourceSnippet: {
    ...typography.bodySm,
    color: colors.onMuted,
    maxWidth: 330,
    textAlign: 'center',
  },
  section: {
    gap: spacing.md,
    marginTop: spacing.xxl,
  },
  sectionTitle: {
    ...typography.headlineMd,
    color: colors.onSurface,
  },
  bookList: {
    gap: spacing.md,
  },
  bookRow: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.md,
    borderWidth: 1,
    flexDirection: 'row',
    gap: spacing.md,
    padding: spacing.card,
  },
  bookCover: {
    alignItems: 'center',
    borderRadius: radius.sm,
    height: 64,
    justifyContent: 'center',
    width: 44,
  },
  bookCoverText: {
    ...typography.labelMd,
    color: colors.onPrimary,
  },
  bookCopy: {
    flex: 1,
    gap: spacing.xs,
  },
  bookTitle: {
    ...typography.titleMd,
    color: colors.onSurface,
  },
  bookAuthor: {
    ...typography.bodySm,
    color: colors.secondary,
  },
  bookSynopsis: {
    ...typography.caption,
    color: colors.onMuted,
  },
  skeletonList: {
    gap: spacing.md,
  },
  skeletonCover: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.sm,
    height: 64,
    width: 44,
  },
  skeletonTextGroup: {
    flex: 1,
    gap: spacing.sm,
  },
  skeletonLine: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.xs,
    height: 10,
  },
  stateCard: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.md,
    borderWidth: 1,
    gap: spacing.md,
    marginTop: spacing.xxl,
    padding: spacing.lg,
  },
  stateTitle: {
    ...typography.titleLg,
    color: colors.onSurface,
  },
  stateBody: {
    ...typography.bodySm,
    color: colors.onMuted,
  },
  stateActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  primaryButton: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    minHeight: 48,
    justifyContent: 'center',
    paddingHorizontal: spacing.lg,
  },
  primaryButtonText: {
    ...typography.labelLg,
    color: colors.onPrimary,
  },
  secondaryButton: {
    alignItems: 'center',
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderRadius: radius.md,
    borderWidth: 1,
    minHeight: 48,
    justifyContent: 'center',
    paddingHorizontal: spacing.lg,
  },
  secondaryButtonText: {
    ...typography.labelLg,
    color: colors.onSurface,
  },
  compactButton: {
    minHeight: 40,
    paddingHorizontal: spacing.md,
  },
  modalOverlay: {
    backgroundColor: 'rgba(20, 32, 27, 0.18)',
    flex: 1,
    justifyContent: 'flex-end',
  },
  bottomSheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    gap: spacing.lg,
    padding: spacing.screen,
    paddingBottom: spacing.xxl,
  },
  sheetHandle: {
    alignSelf: 'center',
    backgroundColor: colors.border,
    borderRadius: 2,
    height: 4,
    width: 42,
  },
  sheetTitle: {
    ...typography.headlineMd,
    color: colors.onSurface,
  },
  sheetBody: {
    ...typography.bodySm,
    color: colors.onMuted,
  },
  accountEmail: {
    ...typography.bodySm,
    color: colors.onMuted,
  },
  sheetMenu: {
    borderColor: colors.border,
    borderRadius: radius.md,
    borderWidth: 1,
    overflow: 'hidden',
  },
  sheetRow: {
    backgroundColor: colors.surface,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    minHeight: 48,
    justifyContent: 'center',
    paddingHorizontal: spacing.md,
  },
  sheetRowText: {
    ...typography.bodyMd,
    color: colors.onSurface,
  },
  destructiveText: {
    color: colors.error,
  },
  inputLabel: {
    ...typography.labelMd,
    color: colors.secondary,
    marginBottom: spacing.xs,
    marginTop: spacing.sm,
  },
  input: {
    ...typography.bodyMd,
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderRadius: radius.md,
    borderWidth: 1,
    color: colors.onSurface,
    minHeight: 48,
    paddingHorizontal: spacing.md,
    marginBottom: spacing.lg,
  },
});
