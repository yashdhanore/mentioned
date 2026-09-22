import type { ReactNode } from 'react';
import { Animated } from 'react-native';
import { useEffect, useRef } from 'react';

import { useReduceMotion } from '@/hooks/use-reduce-motion';

type FadeInViewProps = {
  children: ReactNode;
  delay?: number;
};

export function FadeInView({ children, delay = 0 }: FadeInViewProps) {
  const opacity = useRef(new Animated.Value(0)).current;
  const translateY = useRef(new Animated.Value(8)).current;
  const reduceMotion = useReduceMotion();

  useEffect(() => {
    if (reduceMotion) {
      opacity.setValue(1);
      translateY.setValue(0);
      return undefined;
    }

    const animation = Animated.parallel([
      Animated.timing(opacity, {
        delay,
        duration: 220,
        toValue: 1,
        useNativeDriver: true,
      }),
      Animated.timing(translateY, {
        delay,
        duration: 220,
        toValue: 0,
        useNativeDriver: true,
      }),
    ]);

    animation.start();
    return () => {
      animation.stop();
    };
  }, [delay, opacity, translateY, reduceMotion]);

  return (
    <Animated.View style={{ opacity, transform: [{ translateY }] }}>
      {children}
    </Animated.View>
  );
}
