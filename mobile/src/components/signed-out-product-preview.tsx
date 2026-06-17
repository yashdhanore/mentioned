import { useEffect, useRef, useState } from 'react';
import {
  AccessibilityInfo,
  Animated,
  Easing,
  Image,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';

import { styles } from '@/styles';

const authOrbitReelPreview = require('../../assets/auth-orbit-reel-preview.png');

const orbitBookCovers = {
  atomicHabits: require('../../assets/book-covers/atomic-habits.jpg'),
  deepWork: require('../../assets/book-covers/deep-work.jpg'),
  theTalentCode: require('../../assets/book-covers/the-talent-code.jpg'),
  theShallows: require('../../assets/book-covers/the-shallows.jpg'),
} as const;

const orbitBooks = [
  {
    title: 'Atomic Habits',
    coverSource: orbitBookCovers.atomicHabits,
    positionStyle: styles.authOrbitBookUpperLeft,
    compactPositionStyle: styles.authOrbitBookUpperLeftCompact,
    driftX: 6,
    driftY: -5,
    rotateFrom: '-7deg',
    rotateTo: '-3deg',
  },
  {
    title: 'Deep Work',
    coverSource: orbitBookCovers.deepWork,
    positionStyle: styles.authOrbitBookUpperRight,
    compactPositionStyle: styles.authOrbitBookUpperRightCompact,
    driftX: -5,
    driftY: -4,
    rotateFrom: '6deg',
    rotateTo: '10deg',
  },
  {
    title: 'The Talent Code',
    coverSource: orbitBookCovers.theTalentCode,
    positionStyle: styles.authOrbitBookLowerLeft,
    compactPositionStyle: styles.authOrbitBookLowerLeftCompact,
    driftX: 5,
    driftY: 5,
    rotateFrom: '-10deg',
    rotateTo: '-6deg',
  },
  {
    title: 'The Shallows',
    coverSource: orbitBookCovers.theShallows,
    positionStyle: styles.authOrbitBookLowerRight,
    compactPositionStyle: styles.authOrbitBookLowerRightCompact,
    driftX: -6,
    driftY: 5,
    rotateFrom: '8deg',
    rotateTo: '4deg',
  },
] as const;

export function SignedOutProductPreview() {
  const { width } = useWindowDimensions();
  const isCompact = width < 360;
  const [shouldReduceMotion, setShouldReduceMotion] = useState(false);
  const orbitValues = useRef(orbitBooks.map(() => new Animated.Value(0))).current;

  useEffect(() => {
    let isMounted = true;

    AccessibilityInfo.isReduceMotionEnabled().then((enabled) => {
      if (isMounted) {
        setShouldReduceMotion(enabled);
      }
    });

    const subscription = AccessibilityInfo.addEventListener('reduceMotionChanged', (enabled) => {
      setShouldReduceMotion(enabled);
    });

    return () => {
      isMounted = false;
      subscription.remove();
    };
  }, []);

  useEffect(() => {
    if (shouldReduceMotion) {
      orbitValues.forEach((value) => value.stopAnimation());
      return undefined;
    }

    const animations = orbitValues.map((value, index) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(index * 420),
          Animated.timing(value, {
            duration: 7600 + index * 420,
            easing: Easing.inOut(Easing.sin),
            toValue: 1,
            useNativeDriver: true,
          }),
          Animated.timing(value, {
            duration: 7600 + index * 420,
            easing: Easing.inOut(Easing.sin),
            toValue: 0,
            useNativeDriver: true,
          }),
        ]),
      ),
    );

    animations.forEach((animation) => animation.start());

    return () => {
      animations.forEach((animation) => animation.stop());
    };
  }, [orbitValues, shouldReduceMotion]);

  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={[styles.authProductPreview, isCompact && styles.authProductPreviewCompact]}
    >
      <View
        style={[
          styles.authOrbitGuide,
          styles.authOrbitGuideOuter,
          isCompact && styles.authOrbitGuideOuterCompact,
        ]}
      />
      <View
        style={[
          styles.authOrbitGuide,
          styles.authOrbitGuideInner,
          isCompact && styles.authOrbitGuideInnerCompact,
        ]}
      />

      <View style={[styles.authPreviewReelShell, isCompact && styles.authPreviewReelShellCompact]}>
        <Image source={authOrbitReelPreview} resizeMode="cover" style={styles.authPreviewReelImage} />
        <View style={styles.authPreviewReelMeta}>
          <Text style={styles.authPreviewReelPlay}>{'\u25B6'}</Text>
          <Text style={styles.authPreviewReelCount}>1.2M</Text>
        </View>
      </View>

      {orbitBooks.map((book, index) => {
        const animatedValue = orbitValues[index];
        const compactTransform = isCompact ? [{ scale: 0.8 }] : [];
        const transform = shouldReduceMotion
          ? compactTransform
          : [
              {
                translateX: animatedValue.interpolate({
                  inputRange: [0, 1],
                  outputRange: [book.driftX, -book.driftX],
                }),
              },
              {
                translateY: animatedValue.interpolate({
                  inputRange: [0, 1],
                  outputRange: [book.driftY, -book.driftY],
                }),
              },
              {
                rotate: animatedValue.interpolate({
                  inputRange: [0, 1],
                  outputRange: [book.rotateFrom, book.rotateTo],
                }),
              },
              ...compactTransform,
            ];

        return (
          <Animated.View
            key={book.title}
            style={[
              styles.authOrbitBook,
              book.positionStyle,
              isCompact && book.compactPositionStyle,
              transform.length > 0 && { transform },
            ]}
          >
            <View style={styles.authOrbitBookCover}>
              <Image
                accessibilityLabel={`${book.title} book cover`}
                resizeMode="cover"
                source={book.coverSource}
                style={styles.authOrbitBookImage}
              />
            </View>
          </Animated.View>
        );
      })}
    </View>
  );
}
