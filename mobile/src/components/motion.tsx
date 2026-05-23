import type { ReactNode } from 'react';
import { Animated } from 'react-native';
import { useEffect, useRef } from 'react';

type FadeInViewProps = {
  children: ReactNode;
  delay?: number;
};

export function FadeInView({ children, delay = 0 }: FadeInViewProps) {
  const opacity = useRef(new Animated.Value(0)).current;
  const translateY = useRef(new Animated.Value(8)).current;

  useEffect(() => {
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
  }, [delay, opacity, translateY]);

  return (
    <Animated.View style={{ opacity, transform: [{ translateY }] }}>
      {children}
    </Animated.View>
  );
}
