import Svg, { Ellipse, G, Path } from 'react-native-svg';
import { View } from 'react-native';

import { colors } from '@/theme';
import { styles } from '@/styles';

const VIEWBOX = 100;

// A few overlapping, slightly-rotated elliptical strokes read as a tangled
// weed rather than a clean ring. Drawn in a 100x100 viewBox, centered ~ (50,46)
// with a flat contact shadow below at y~84.
function TumbleweedArt({ size = 96 }: { size?: number }) {
  return (
    <Svg width={size} height={size} viewBox={`0 0 ${VIEWBOX} ${VIEWBOX}`}>
      {/* static ground shadow */}
      <Ellipse cx={50} cy={86} rx={30} ry={5} fill={colors.ink} opacity={0.06} />
      <G
        stroke={colors.secondary}
        strokeWidth={1.5}
        fill="none"
        strokeLinecap="round"
      >
        <Ellipse cx={50} cy={46} rx={30} ry={30} />
        <Ellipse cx={50} cy={46} rx={29} ry={18} transform="rotate(28 50 46)" />
        <Ellipse cx={50} cy={46} rx={29} ry={18} transform="rotate(-34 50 46)" />
        <Ellipse cx={50} cy={46} rx={18} ry={29} transform="rotate(12 50 46)" />
        {/* a couple of stray strands so it reads organic, not geometric */}
        <Path d="M24 34 Q40 50 30 64" />
        <Path d="M76 34 Q60 48 70 66" />
        <Path d="M38 22 Q52 44 64 24" />
      </G>
    </Svg>
  );
}

export function Tumbleweed({ size = 96 }: { size?: number }) {
  return (
    <View style={styles.tumbleweedWrap}>
      <TumbleweedArt size={size} />
    </View>
  );
}
