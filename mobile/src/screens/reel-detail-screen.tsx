import { useEffect, useRef, useState } from 'react';
import { AccessibilityInfo, Animated, Easing, Image, Pressable, ScrollView, Text, View } from 'react-native';

import { sourceIdentityLabel, type Capture } from '@/captures';
import { BackIcon, ExternalLinkIcon, MoreIcon } from '@/components/icons';
import {
  FailedState,
  MentionsList,
  NoMentions,
  ProcessingMentions,
} from '@/components/mentions';
import { AppMark, IconButton, InlineMessage, SecondaryButton } from '@/components/ui';
import { styles as sharedStyles } from '@/styles';
import { styles as localStyles } from './reel-detail-screen.styles';

const styles = { ...sharedStyles, ...localStyles };

export function ReelDetailScreen({
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
  const sourcePreviewWidth = Math.min(Math.max(width * 0.32, 96), 124);
  const sourceHeroWidth = Math.min(Math.max(width * 0.58, 210), 260);
  const inlineError = actionError ? <InlineMessage tone="error" message={actionError} /> : null;

  return (
    <ScrollView
      contentContainerStyle={styles.detailContent}
      showsVerticalScrollIndicator={false}
      bounces
    >
      <View style={styles.detailNav}>
        <IconButton accessibilityLabel="Back to saved items" onPress={onBack}>
          <BackIcon />
        </IconButton>
        <SourceNavIdentity capture={capture} />
        <IconButton accessibilityLabel="Open post actions" onPress={onOpenMenu}>
          <MoreIcon />
        </IconButton>
      </View>

      {capture.status === 'ready' ? (
        <>
          <SourceHero
            capture={capture}
            previewWidth={sourceHeroWidth}
            onOpenSource={onOpenSource}
          />
          {inlineError}
          <MentionsList mentions={capture.mentions} />
        </>
      ) : null}
      {capture.status === 'processing' ? (
        <>
          {inlineError}
          <ProcessingMentions />
          <ProcessingBrandMark />
        </>
      ) : null}
      {capture.status === 'no_mentions' ? (
        <>
          {inlineError}
          <NoMentions onOpenSource={onOpenSource} wasSkipped={Boolean(capture.skipReason)} />
          <OriginalSourceSection
            capture={capture}
            previewWidth={sourcePreviewWidth}
            onOpenSource={onOpenSource}
          />
        </>
      ) : null}
      {capture.status === 'failed' ? (
        <>
          {inlineError}
          <FailedState isRetrying={isRetrying} onOpenSource={onOpenSource} onRetry={onRetry} />
          <OriginalSourceSection
            capture={capture}
            previewWidth={sourcePreviewWidth}
            onOpenSource={onOpenSource}
          />
        </>
      ) : null}
    </ScrollView>
  );
}

function SourceNavIdentity({ capture }: { capture: Capture }) {
  const label = sourceIdentityLabel(capture);

  return (
    <View style={styles.detailNavIdentity}>
      {capture.creatorHandle && capture.thumbnailUrl ? (
        <Image
          source={{ uri: capture.thumbnailUrl }}
          resizeMode="cover"
          style={styles.detailNavAvatar}
        />
      ) : null}
      <Text
        numberOfLines={1}
        style={capture.creatorHandle ? styles.detailNavHandle : styles.detailNavTitle}
      >
        {label}
      </Text>
    </View>
  );
}

function SourceHero({
  capture,
  previewWidth,
  onOpenSource,
}: {
  capture: Capture;
  previewWidth: number;
  onOpenSource: () => void;
}) {
  const savedLabel = savedAtLabel(capture.createdAt);

  return (
    <View style={styles.sourceHero}>
      <View style={styles.sourceHeroStage}>
        <View style={styles.sourceHeroPaper} />
        <View style={[styles.sourceHeroCard, { width: previewWidth }]}>
          {capture.thumbnailUrl ? (
            <Image
              source={{ uri: capture.thumbnailUrl }}
              resizeMode="cover"
              style={styles.sourceHeroImage}
            />
          ) : (
            <View style={styles.thumbnailFallback}>
              <AppMark style={styles.thumbnailFallbackMark} />
            </View>
          )}
        </View>
      </View>

      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Open original post"
        style={({ pressed }) => [styles.sourceHeroAction, pressed && styles.pressed]}
        onPress={onOpenSource}
      >
        <Text style={styles.sourceHeroActionText}>Open post</Text>
        <ExternalLinkIcon color="#0E6F68" size={18} />
      </Pressable>

      <View style={styles.sourceHeroMeta}>
        <View style={styles.sourceHeroIdentity}>
          <Text numberOfLines={1} style={styles.sourceHeroCreator}>
            {sourceIdentityLabel(capture)}
          </Text>
          {savedLabel ? (
            <Text numberOfLines={1} style={styles.sourceHeroSavedAt}>
              {savedLabel}
            </Text>
          ) : null}
        </View>
      </View>
    </View>
  );
}

function savedAtLabel(createdAt: string): string | null {
  const timestamp = Date.parse(createdAt);
  if (!Number.isFinite(timestamp)) {
    return null;
  }

  const diffMs = Math.max(0, Date.now() - timestamp);
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;

  if (diffMs < minute) {
    return 'Saved just now';
  }
  if (diffMs < hour) {
    return `Saved ${Math.floor(diffMs / minute)}m ago`;
  }
  if (diffMs < day) {
    return `Saved ${Math.floor(diffMs / hour)}h ago`;
  }
  if (diffMs < 7 * day) {
    return `Saved ${Math.floor(diffMs / day)}d ago`;
  }

  return `Saved ${new Date(timestamp).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
  })}`;
}

function ProcessingBrandMark() {
  const opacity = useRef(new Animated.Value(0.45)).current;
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    let isMounted = true;
    const subscription = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduceMotion);

    void AccessibilityInfo.isReduceMotionEnabled().then((isReduceMotionEnabled) => {
      if (isMounted) {
        setReduceMotion(isReduceMotionEnabled);
      }
    });

    return () => {
      isMounted = false;
      subscription.remove();
    };
  }, []);

  useEffect(() => {
    if (reduceMotion) {
      opacity.setValue(1);
      return undefined;
    }

    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, {
          toValue: 1,
          duration: 800,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(opacity, {
          toValue: 0.45,
          duration: 800,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
      ]),
    );

    animation.start();

    return () => animation.stop();
  }, [opacity, reduceMotion]);

  return (
    <View style={styles.processingBrandMarkWrap}>
      <Animated.View style={{ opacity }}>
        <AppMark size={56} style={styles.processingBrandMark} />
      </Animated.View>
    </View>
  );
}

function OriginalSourceSection({
  capture,
  previewWidth,
  onOpenSource,
}: {
  capture: Capture;
  previewWidth: number;
  onOpenSource: () => void;
}) {
  return (
    <View style={styles.originalSourceSection}>
      <Text style={styles.originalSourceTitle}>Original post</Text>
      <View style={styles.originalSourceModule}>
        <View style={[styles.originalSourcePreview, { width: previewWidth }]}>
          {capture.thumbnailUrl ? (
            <Image source={{ uri: capture.thumbnailUrl }} style={styles.reelPreviewImage} />
          ) : (
            <View style={styles.thumbnailFallback}>
              <AppMark style={styles.thumbnailFallbackMark} />
            </View>
          )}
        </View>
        <View style={styles.originalSourceCopy}>
          <Text numberOfLines={1} style={styles.sourceCreator}>
            {sourceIdentityLabel(capture)}
          </Text>
          <View style={styles.detailSourceAction}>
            <SecondaryButton label="Open original" onPress={onOpenSource} compact />
          </View>
        </View>
      </View>
    </View>
  );
}
