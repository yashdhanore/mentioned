import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  KeyboardAvoidingView,
  Linking,
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

import {
  DEV_USER_ID,
  createJob,
  errorMessage,
  getJobResult,
  listAllJobs,
  listAllMentions,
  rerunJob,
} from './src/api';
import {
  applyResultFallback,
  buildCaptures,
  captureFromJob,
  type BookMention,
  type Capture,
} from './src/captures';
import { colors, radius, spacing, typography } from './src/theme';

type Sheet = 'profile' | 'paste' | 'reelMenu' | null;

export default function App() {
  const { width } = useWindowDimensions();
  const [isSignedIn, setIsSignedIn] = useState(false);
  const [captures, setCaptures] = useState<Capture[]>([]);
  const [selectedCaptureId, setSelectedCaptureId] = useState<string | null>(null);
  const [sheet, setSheet] = useState<Sheet>(null);
  const [pasteUrl, setPasteUrl] = useState('');
  const [isLoadingCaptures, setIsLoadingCaptures] = useState(false);
  const [isSubmittingUrl, setIsSubmittingUrl] = useState(false);
  const [retryingCaptureId, setRetryingCaptureId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pasteError, setPasteError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const tileWidth = useMemo(() => {
    return (width - spacing.screen * 2 - spacing.md) / 2;
  }, [width]);

  const selectedCapture = useMemo(() => {
    return captures.find((capture) => capture.id === selectedCaptureId) ?? null;
  }, [captures, selectedCaptureId]);

  const refreshCaptures = useCallback(
    async ({ silent = false }: { silent?: boolean } = {}) => {
      if (!isSignedIn) {
        return;
      }

      if (!silent) {
        setIsLoadingCaptures(true);
      }
      setLoadError(null);

      try {
        const [jobs, mentions] = await Promise.all([listAllJobs(), listAllMentions()]);
        setCaptures(buildCaptures(jobs, mentions));
      } catch (error) {
        setLoadError(errorMessage(error, 'Could not load saved Reels.'));
      } finally {
        if (!silent) {
          setIsLoadingCaptures(false);
        }
      }
    },
    [isSignedIn],
  );

  useEffect(() => {
    if (!isSignedIn) {
      setCaptures([]);
      setSelectedCaptureId(null);
      return;
    }

    void refreshCaptures();
  }, [isSignedIn, refreshCaptures]);

  useEffect(() => {
    if (!isSignedIn || !captures.some((capture) => capture.status === 'processing')) {
      return undefined;
    }

    const intervalId = setInterval(() => {
      void refreshCaptures({ silent: true });
    }, 4000);

    return () => clearInterval(intervalId);
  }, [captures, isSignedIn, refreshCaptures]);

  const openCapture = useCallback((capture: Capture) => {
    setActionError(null);
    setSelectedCaptureId(capture.id);

    if (!capture.sourceContextSnippet && capture.status !== 'processing') {
      void getJobResult(capture.id)
        .then((result) => {
          setCaptures((current) =>
            current.map((item) => (item.id === capture.id ? applyResultFallback(item, result) : item)),
          );
        })
        .catch(() => undefined);
    }
  }, []);

  const submitPasteUrl = useCallback(async () => {
    const url = pasteUrl.trim();
    if (!url) {
      setPasteError('Paste an Instagram Reel or post URL.');
      return;
    }

    setPasteError(null);
    setIsSubmittingUrl(true);

    try {
      const created = await createJob(url);
      const capture = captureFromJob(created);
      setCaptures((current) => [capture, ...current.filter((item) => item.id !== capture.id)]);
      setSelectedCaptureId(capture.id);
      setPasteUrl('');
      setSheet(null);
      void refreshCaptures({ silent: true });
    } catch (error) {
      setPasteError(errorMessage(error, 'Could not submit that Reel.'));
    } finally {
      setIsSubmittingUrl(false);
    }
  }, [pasteUrl, refreshCaptures]);

  const retryCapture = useCallback(
    async (capture: Capture) => {
      setActionError(null);
      setRetryingCaptureId(capture.id);

      try {
        const rerun = await rerunJob(capture.id);
        const processingCapture = captureFromJob(rerun);
        setCaptures((current) =>
          current.map((item) => (item.id === capture.id ? { ...processingCapture, thumbnailUrl: item.thumbnailUrl } : item)),
        );
        void refreshCaptures({ silent: true });
      } catch (error) {
        setActionError(errorMessage(error, 'Could not retry this Reel.'));
      } finally {
        setRetryingCaptureId(null);
      }
    },
    [refreshCaptures],
  );

  const openSource = useCallback(async (capture: Capture) => {
    setActionError(null);
    try {
      await Linking.openURL(capture.sourceUrl);
    } catch (error) {
      setActionError(errorMessage(error, 'Could not open the source URL.'));
    }
  }, []);

  if (!isSignedIn) {
    return <SignedOutScreen onContinue={() => setIsSignedIn(true)} />;
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      {selectedCapture ? (
        <ReelDetail
          capture={selectedCapture}
          width={width}
          actionError={actionError}
          isRetrying={retryingCaptureId === selectedCapture.id}
          onBack={() => setSelectedCaptureId(null)}
          onOpenMenu={() => setSheet('reelMenu')}
          onOpenSource={() => void openSource(selectedCapture)}
          onRetry={() => void retryCapture(selectedCapture)}
        />
      ) : (
        <HomeScreen
          captures={captures}
          error={loadError}
          isLoading={isLoadingCaptures}
          tileWidth={tileWidth}
          onOpenPaste={() => setSheet('paste')}
          onOpenProfile={() => setSheet('profile')}
          onOpenCapture={openCapture}
          onRefresh={() => void refreshCaptures()}
        />
      )}

      <ProfileSheet visible={sheet === 'profile'} onClose={() => setSheet(null)} />
      <PasteSheet
        visible={sheet === 'paste'}
        error={pasteError}
        isSubmitting={isSubmittingUrl}
        value={pasteUrl}
        onChange={(value) => {
          setPasteError(null);
          setPasteUrl(value);
        }}
        onClose={() => {
          setPasteError(null);
          setSheet(null);
        }}
        onSubmit={submitPasteUrl}
      />
      <ReelMenuSheet
        visible={sheet === 'reelMenu'}
        onClose={() => setSheet(null)}
        onOpenSource={selectedCapture ? () => void openSource(selectedCapture) : undefined}
      />
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
  captures,
  error,
  isLoading,
  tileWidth,
  onOpenPaste,
  onOpenProfile,
  onOpenCapture,
  onRefresh,
}: {
  captures: Capture[];
  error: string | null;
  isLoading: boolean;
  tileWidth: number;
  onOpenPaste: () => void;
  onOpenProfile: () => void;
  onOpenCapture: (capture: Capture) => void;
  onRefresh: () => void;
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

      {error ? <InlineMessage tone="error" message={error} actionLabel="Try again" onAction={onRefresh} /> : null}

      {isLoading && captures.length === 0 ? <LoadingState /> : null}
      {!isLoading && captures.length === 0 ? <EmptyCaptures onOpenPaste={onOpenPaste} /> : null}

      {captures.length > 0 ? (
        <View style={styles.grid}>
          {captures.map((capture) => (
            <ReelTile
              key={capture.id}
              capture={capture}
              width={tileWidth}
              onPress={() => onOpenCapture(capture)}
            />
          ))}
        </View>
      ) : null}
    </ScrollView>
  );
}

function LoadingState() {
  return (
    <View style={styles.loadingState}>
      <ActivityIndicator color={colors.primary} />
      <Text style={styles.loadingText}>Loading saved Reels...</Text>
    </View>
  );
}

function EmptyCaptures({ onOpenPaste }: { onOpenPaste: () => void }) {
  return (
    <View style={styles.stateCard}>
      <Text style={styles.stateTitle}>No saved Reels yet</Text>
      <Text style={styles.stateBody}>Paste an Instagram Reel or post link to start finding books.</Text>
      <View style={styles.stateActions}>
        <PrimaryButton label="Paste link" onPress={onOpenPaste} compact />
      </View>
    </View>
  );
}

function ReelTile({ capture, width, onPress }: { capture: Capture; width: number; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${capture.creator} saved Reel`}
      style={({ pressed }) => [styles.reelTile, { width }, pressed && styles.pressed]}
      onPress={onPress}
    >
      <Image source={{ uri: capture.thumbnailUrl }} style={styles.reelTileImage} />
      <View style={styles.reelTileScrim} />
      {capture.status !== 'ready' ? <TileStatus status={capture.status} /> : null}
      <Text numberOfLines={1} style={styles.reelCreator}>
        {capture.creator}
      </Text>
    </Pressable>
  );
}

function TileStatus({ status }: { status: Capture['status'] }) {
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
  capture,
  width,
  actionError,
  isRetrying,
  onBack,
  onOpenMenu,
  onOpenSource,
  onRetry,
}: {
  capture: Capture;
  width: number;
  actionError: string | null;
  isRetrying: boolean;
  onBack: () => void;
  onOpenMenu: () => void;
  onOpenSource: () => void;
  onRetry: () => void;
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
          {capture.creator}
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
          <Image source={{ uri: capture.thumbnailUrl }} style={styles.reelPreviewImage} />
        </View>
      </View>

      <View style={styles.sourceBlock}>
        <Text style={styles.sourceCreator}>{capture.creator}</Text>
        {capture.sourceContextSnippet ? (
          <Text numberOfLines={2} style={styles.sourceSnippet}>
            {capture.sourceContextSnippet}
          </Text>
        ) : null}
      </View>

      {actionError ? <InlineMessage tone="error" message={actionError} /> : null}

      {capture.status === 'processing' ? <ProcessingBooks /> : null}
      {capture.status === 'ready' ? <BooksMentioned books={capture.books} /> : null}
      {capture.status === 'no_books' ? <NoBooks onOpenSource={onOpenSource} /> : null}
      {capture.status === 'failed' ? (
        <FailedState isRetrying={isRetrying} onOpenSource={onOpenSource} onRetry={onRetry} />
      ) : null}
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

function BooksMentioned({ books: mentionedBooks }: { books: BookMention[] }) {
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

function NoBooks({ onOpenSource }: { onOpenSource: () => void }) {
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

function FailedState({
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

function ProfileSheet({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  return (
    <BottomSheet visible={visible} onClose={onClose}>
      <Text style={styles.sheetTitle}>Profile</Text>
      <Text style={styles.accountEmail}>Dev user {DEV_USER_ID}</Text>
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
  error,
  isSubmitting,
  value,
  onChange,
  onClose,
  onSubmit,
}: {
  visible: boolean;
  error: string | null;
  isSubmitting: boolean;
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
        {error ? <InlineMessage tone="error" message={error} /> : null}
        <PrimaryButton
          label={isSubmitting ? 'Finding books...' : 'Find books'}
          onPress={onSubmit}
          disabled={isSubmitting}
        />
      </KeyboardAvoidingView>
    </BottomSheet>
  );
}

function ReelMenuSheet({
  visible,
  onClose,
  onOpenSource,
}: {
  visible: boolean;
  onClose: () => void;
  onOpenSource?: () => void;
}) {
  return (
    <BottomSheet visible={visible} onClose={onClose}>
      <Text style={styles.sheetTitle}>Reel actions</Text>
      <View style={styles.sheetMenu}>
        <SheetRow
          label="Open source"
          onPress={() => {
            onOpenSource?.();
            onClose();
          }}
        />
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

function SheetRow({
  label,
  destructive = false,
  onPress,
}: {
  label: string;
  destructive?: boolean;
  onPress?: () => void;
}) {
  return (
    <Pressable style={({ pressed }) => [styles.sheetRow, pressed && styles.pressed]} onPress={onPress}>
      <Text style={[styles.sheetRowText, destructive && styles.destructiveText]}>{label}</Text>
    </Pressable>
  );
}

function PrimaryButton({
  label,
  onPress,
  compact = false,
  disabled = false,
}: {
  label: string;
  onPress: () => void;
  compact?: boolean;
  disabled?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      style={({ pressed }) => [
        styles.primaryButton,
        compact && styles.compactButton,
        disabled && styles.disabledButton,
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
  disabled = false,
}: {
  label: string;
  onPress: () => void;
  compact?: boolean;
  disabled?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      style={({ pressed }) => [
        styles.secondaryButton,
        compact && styles.compactButton,
        disabled && styles.disabledButton,
        pressed && styles.pressed,
      ]}
      onPress={onPress}
    >
      <Text style={styles.secondaryButtonText}>{label}</Text>
    </Pressable>
  );
}

function InlineMessage({
  message,
  tone,
  actionLabel,
  onAction,
}: {
  message: string;
  tone: 'error' | 'warning';
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <View style={[styles.inlineMessage, tone === 'error' ? styles.inlineError : styles.inlineWarning]}>
      <Text style={[styles.inlineMessageText, tone === 'error' ? styles.inlineErrorText : styles.inlineWarningText]}>
        {message}
      </Text>
      {actionLabel && onAction ? (
        <Pressable
          accessibilityRole="button"
          style={({ pressed }) => [styles.inlineAction, pressed && styles.pressed]}
          onPress={onAction}
        >
          <Text style={styles.inlineActionText}>{actionLabel}</Text>
        </Pressable>
      ) : null}
    </View>
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
  loadingState: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.md,
    borderWidth: 1,
    gap: spacing.sm,
    padding: spacing.lg,
  },
  loadingText: {
    ...typography.bodySm,
    color: colors.onMuted,
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
  disabledButton: {
    opacity: 0.55,
  },
  inlineMessage: {
    borderRadius: radius.md,
    borderWidth: 1,
    gap: spacing.sm,
    padding: spacing.md,
  },
  inlineError: {
    backgroundColor: colors.errorSoft,
    borderColor: colors.error,
  },
  inlineWarning: {
    backgroundColor: colors.warningSoft,
    borderColor: colors.warning,
  },
  inlineMessageText: {
    ...typography.bodySm,
  },
  inlineErrorText: {
    color: colors.error,
  },
  inlineWarningText: {
    color: colors.warning,
  },
  inlineAction: {
    alignSelf: 'flex-start',
  },
  inlineActionText: {
    ...typography.labelMd,
    color: colors.primary,
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
