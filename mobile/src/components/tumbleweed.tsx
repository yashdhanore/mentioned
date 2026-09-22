import { useEffect, useRef } from 'react';
import { Animated, View } from 'react-native';
import Svg, { Ellipse, G, Path } from 'react-native-svg';

import { colors } from '@/theme';
import { useReduceMotion } from '@/hooks/use-reduce-motion';
import { styles } from './tumbleweed.styles';

const VIEWBOX = 100;

// The weed: overlapping, slightly-rotated elliptical strokes read as a tangled
// ball rather than a clean ring. This layer is what sways.
function TumbleweedArt({ size }: { size: number }) {
  return (
    <Svg width={size} height={size} viewBox={`0 0 ${VIEWBOX} ${VIEWBOX}`}>
      <G stroke={colors.secondary} strokeWidth={1.5} fill="none" strokeLinecap="round">
        <Ellipse cx={50} cy={46} rx={30} ry={30} />
        <Ellipse cx={50} cy={46} rx={29} ry={18} transform="rotate(28 50 46)" />
        <Ellipse cx={50} cy={46} rx={29} ry={18} transform="rotate(-34 50 46)" />
        <Ellipse cx={50} cy={46} rx={18} ry={29} transform="rotate(12 50 46)" />
        <Path d="M24 34 Q40 50 30 64" />
        <Path d="M76 34 Q60 48 70 66" />
        <Path d="M38 22 Q52 44 64 24" />
      </G>
    </Svg>
  );
}

// Separate static layer so the contact shadow does NOT move when the weed sways.
function GroundShadow({ size }: { size: number }) {
  return (
    <Svg width={size} height={size} viewBox={`0 0 ${VIEWBOX} ${VIEWBOX}`}>
      <Ellipse cx={50} cy={86} rx={30} ry={5} fill={colors.ink} opacity={0.06} />
    </Svg>
  );
}

export function Tumbleweed({ size = 96 }: { size?: number }) {
  const sway = useRef(new Animated.Value(0)).current;
  const reduceMotion = useReduceMotion();

  useEffect(() => {
    if (reduceMotion) {
      sway.stopAnimation();
      sway.setValue(0);
      return;
    }
    // 0 -> 1 -> 0 maps to rotate -4deg .. +4deg; slow so it breathes, not ticks.
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(sway, {
          toValue: 1,
          duration: 2200,
          useNativeDriver: true,
        }),
        Animated.timing(sway, {
          toValue: 0,
          duration: 2200,
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [reduceMotion, sway]);

  const rotate = sway.interpolate({
    inputRange: [0, 1],
    outputRange: ['-4deg', '4deg'],
  });
  const translateX = sway.interpolate({
    inputRange: [0, 1],
    outputRange: [-1.5, 1.5],
  });

  return (
    <View
      style={styles.tumbleweedWrap}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      <View style={styles.tumbleweedShadow} pointerEvents="none">
        <GroundShadow size={size} />
      </View>
      <Animated.View style={{ transform: [{ rotate }, { translateX }] }}>
        <TumbleweedArt size={size} />
      </Animated.View>
    </View>
  );
}
