# Empty-state Tumbleweed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the home-screen "No saved posts yet" card with a full-scene empty state featuring an on-brand line-art SVG tumbleweed that gently sways, playful desert copy, and a reduce-motion guard.

**Architecture:** Component-per-concern (mirrors existing `product-preview.tsx` / `motion.tsx`). A self-contained `Tumbleweed` SVG component owns its drawing + sway animation. A new `empty-state.tsx` composes the scene (weed + copy + Paste button). `home-screen.tsx` swaps its inline `EmptyCaptures` for the new component and drops the `SourceToBooksPreview` demo.

**Tech Stack:** React Native (Expo), TypeScript, `react-native-svg` (already a dependency, v15.12.1), RN built-in `Animated` API (no new deps), `AccessibilityInfo` for reduce-motion.

**Testing note:** The mobile package has **no unit-test framework** (no jest/testing-library; "tests" are standalone `tsx` scripts). The only automated gate is `npm run typecheck`. Verification in this plan is therefore typecheck + explicit manual runtime checks, not unit tests. Do not invent jest tests.

---

## File Structure

- **Create** `mobile/src/components/tumbleweed.tsx` — the SVG tumbleweed + its sway animation + reduce-motion guard. One responsibility: render an animated weed.
- **Create** `mobile/src/components/empty-state.tsx` — composes the full empty scene (weed, headline, subline, Paste button). Exports `EmptyCaptures`.
- **Modify** `mobile/src/screens/home-screen.tsx` — import `EmptyCaptures` from the new file; delete the inline `EmptyCaptures` function and the now-unused `SourceToBooksPreview` import.
- **Modify** `mobile/src/styles.ts` — add empty-scene styles; remove `emptyPreviewWrap` if unused after the swap.

---

## Task 1: Tumbleweed SVG component (static, no animation yet)

Build and render the weed as a static SVG first, so the drawing can be eyeballed before motion is added.

**Files:**
- Create: `mobile/src/components/tumbleweed.tsx`

- [ ] **Step 1: Create the static Tumbleweed component**

Create `mobile/src/components/tumbleweed.tsx`:

```tsx
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
```

- [ ] **Step 2: Add the wrapper style**

In `mobile/src/styles.ts`, add to the `StyleSheet.create({ ... })` object (place near the other empty-state styles, e.g. after `emptyPreviewWrap`):

```ts
  tumbleweedWrap: {
    alignItems: 'center',
    justifyContent: 'center',
  },
```

- [ ] **Step 3: Typecheck**

Run: `cd mobile && npm run typecheck`
Expected: PASS (no errors). If `react-native-svg` types complain about `transform` as a string, confirm the import path is `react-native-svg` and the prop is passed as a string exactly as above (react-native-svg accepts SVG `transform` strings).

- [ ] **Step 4: Commit**

```bash
git add mobile/src/components/tumbleweed.tsx mobile/src/styles.ts
git commit -m "Add static tumbleweed SVG component"
```

---

## Task 2: Add the gentle idle-sway animation + reduce-motion guard

Animate the weed (not the shadow) with a small looping rotate+translate, and freeze it when the OS reduce-motion setting is on. The ground shadow is split into its own static SVG layer behind the swaying weed so it stays put.

**Files:**
- Modify: `mobile/src/components/tumbleweed.tsx`

- [ ] **Step 1: Replace the component with the animated, shadow-static version**

Replace the entire contents of `mobile/src/components/tumbleweed.tsx` with:

```tsx
import { useEffect, useRef, useState } from 'react';
import { AccessibilityInfo, Animated, View } from 'react-native';
import Svg, { Ellipse, G, Path } from 'react-native-svg';

import { colors } from '@/theme';
import { styles } from '@/styles';

const VIEWBOX = 100;

// The weed: overlapping, slightly-rotated elliptical strokes read as a tangled
// ball rather than a clean ring. This layer is what sways.
function TumbleweedArt({ size }: { size: number }) {
  return (
    <Svg width={size} height={size} viewBox={`0 0 ${VIEWBOX} ${VIEWBOX}`}>
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
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    let mounted = true;
    AccessibilityInfo.isReduceMotionEnabled().then((enabled) => {
      if (mounted) {
        setReduceMotion(enabled);
      }
    });
    const sub = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduceMotion);
    return () => {
      mounted = false;
      sub.remove();
    };
  }, []);

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
    <View style={styles.tumbleweedWrap}>
      <View style={styles.tumbleweedShadow} pointerEvents="none">
        <GroundShadow size={size} />
      </View>
      <Animated.View style={{ transform: [{ rotate }, { translateX }] }}>
        <TumbleweedArt size={size} />
      </Animated.View>
    </View>
  );
}
```

- [ ] **Step 2: Add the shadow-layer style**

In `mobile/src/styles.ts`, add alongside `tumbleweedWrap`:

```ts
  tumbleweedShadow: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
  },
```

Confirm `StyleSheet` is already imported in `styles.ts` (it is — the file calls `StyleSheet.create`). If `absoluteFillObject` causes the shadow to mis-center relative to the weed, instead use explicit positioning; but absolute fill + center should align both SVGs (same viewBox/size).

- [ ] **Step 3: Typecheck**

Run: `cd mobile && npm run typecheck`
Expected: PASS. If `AccessibilityInfo.addEventListener('reduceMotionChanged', ...)` return type errors, confirm RN version exposes the subscription `.remove()` API (it does in Expo SDK's RN); the handler signature is `(enabled: boolean) => void`, matching `setReduceMotion`.

- [ ] **Step 4: Commit**

```bash
git add mobile/src/components/tumbleweed.tsx mobile/src/styles.ts
git commit -m "Animate tumbleweed with gentle sway and reduce-motion guard"
```

---

## Task 3: Empty-state scene component

Compose the full scene: swaying weed + headline + subline + Paste button, faded in on mount.

**Files:**
- Create: `mobile/src/components/empty-state.tsx`
- Modify: `mobile/src/styles.ts`

- [ ] **Step 1: Create the empty-state component**

Create `mobile/src/components/empty-state.tsx`:

```tsx
import { Text, View } from 'react-native';

import { FadeInView } from '@/components/motion';
import { Tumbleweed } from '@/components/tumbleweed';
import { PrimaryButton } from '@/components/ui';
import { styles } from '@/styles';

export function EmptyCaptures({ onOpenPaste }: { onOpenPaste: () => void }) {
  return (
    <FadeInView>
      <View style={styles.emptyScene}>
        <Tumbleweed />
        <Text style={styles.emptySceneTitle}>Sure looks empty out here</Text>
        <Text style={styles.emptySceneBody}>
          Share a reel and Mentioned will round up the books mentioned inside.
        </Text>
        <View style={styles.emptySceneActions}>
          <PrimaryButton label="Paste link" onPress={onOpenPaste} compact />
        </View>
      </View>
    </FadeInView>
  );
}
```

- [ ] **Step 2: Add the scene styles**

In `mobile/src/styles.ts`, add:

```ts
  emptyScene: {
    alignItems: 'center',
    gap: spacing.md,
    marginTop: spacing.xxl,
    paddingHorizontal: spacing.lg,
  },
  emptySceneTitle: {
    ...typography.titleLg,
    color: colors.onSurface,
    marginTop: spacing.sm,
    textAlign: 'center',
  },
  emptySceneBody: {
    ...typography.bodySm,
    color: colors.onMuted,
    maxWidth: 280,
    textAlign: 'center',
  },
  emptySceneActions: {
    marginTop: spacing.sm,
  },
```

Confirm `spacing`, `typography`, and `colors` are already imported at the top of `styles.ts` (they are — existing styles like `stateCard`/`stateTitle` use them).

- [ ] **Step 3: Typecheck**

Run: `cd mobile && npm run typecheck`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add mobile/src/components/empty-state.tsx mobile/src/styles.ts
git commit -m "Add tumbleweed empty-state scene component"
```

---

## Task 4: Wire into home screen, remove old card + demo

Swap the inline `EmptyCaptures` for the new component and drop the now-unused preview.

**Files:**
- Modify: `mobile/src/screens/home-screen.tsx`

- [ ] **Step 1: Update imports**

In `mobile/src/screens/home-screen.tsx`:
- Remove the line: `import { SourceToBooksPreview } from '@/components/product-preview';`
- Add the line (with the other `@/components` imports): `import { EmptyCaptures } from '@/components/empty-state';`

- [ ] **Step 2: Delete the inline EmptyCaptures function**

Delete the entire inline function at the bottom of the file (currently ~lines 131-144):

```tsx
function EmptyCaptures({ onOpenPaste }: { onOpenPaste: () => void }) {
  return (
    <View style={styles.stateCard}>
      <Text style={styles.stateTitle}>No saved posts yet</Text>
      <Text style={styles.stateBody}>Share a post to save it here and start finding books mentioned inside.</Text>
      <View style={styles.emptyPreviewWrap}>
        <SourceToBooksPreview />
      </View>
      <View style={styles.stateActions}>
        <PrimaryButton label="Paste link" onPress={onOpenPaste} compact />
      </View>
    </View>
  );
}
```

The render site at line ~98 (`{!isLoading && captures.length === 0 ? <EmptyCaptures onOpenPaste={onOpenPaste} /> : null}`) stays unchanged — it now resolves to the imported component.

- [ ] **Step 3: Typecheck**

Run: `cd mobile && npm run typecheck`
Expected: PASS. If typecheck reports `PrimaryButton` is now unused in `home-screen.tsx`, leave it only if other call sites use it; otherwise remove `PrimaryButton` from the `@/components/ui` import. (Check first: `rg -n "PrimaryButton" mobile/src/screens/home-screen.tsx` — if the only hit was the deleted function, drop it from the import.)

- [ ] **Step 4: Commit**

```bash
git add mobile/src/screens/home-screen.tsx
git commit -m "Render tumbleweed empty state on home screen"
```

---

## Task 5: Remove dead `emptyPreviewWrap` style if orphaned

**Files:**
- Modify: `mobile/src/styles.ts`

- [ ] **Step 1: Check for remaining consumers**

Run: `rg -n "emptyPreviewWrap" mobile/src`
- If the ONLY hit is the style definition in `styles.ts`, it is now dead — proceed to Step 2.
- If any `.tsx` still references it, STOP and leave it (skip this task).

- [ ] **Step 2: Remove the orphaned style**

Delete the `emptyPreviewWrap` block from `mobile/src/styles.ts`:

```ts
  emptyPreviewWrap: {
    alignItems: 'center',
    overflow: 'hidden',
    paddingVertical: spacing.sm,
  },
```

Do NOT touch `statePreviewWrap`, `stateCard`, `stateTitle`, `stateBody`, or `stateActions` — those are used by other states (loading/pending) and the signed-out screen.

- [ ] **Step 3: Typecheck**

Run: `cd mobile && npm run typecheck`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add mobile/src/styles.ts
git commit -m "Remove orphaned emptyPreviewWrap style"
```

---

## Task 6: Manual runtime verification

No automated UI tests exist; verify on a running app.

- [ ] **Step 1: Launch the app**

Run: `cd mobile && npm run ios` (or `npm run web` for a quick visual check).

- [ ] **Step 2: Reach the empty state**

Sign in with an account that has zero saved posts (or temporarily hardcode the empty branch). Confirm:
- The scene is vertically centered and horizontally centered.
- The tumbleweed renders as a tangled line-art ball in sage/green (`#4E5D57`), with a soft static shadow beneath it.
- The weed sways gently (small rotate + drift), the shadow stays put.
- Headline reads "Sure looks empty out here"; subline reads "Share a reel and Mentioned will round up the books mentioned inside."
- The "Paste link" button opens the paste sheet.
- The whole scene fades in on mount.

- [ ] **Step 3: Verify reduce-motion**

Enable iOS Settings → Accessibility → Motion → Reduce Motion (or the simulator equivalent). Reload the app, reach the empty state, and confirm the weed is **static** (no sway) while the scene and copy still render.

- [ ] **Step 4 (optional): Verify regression on populated state**

Add a saved post and confirm the grid renders normally (empty branch no longer shows). No commit needed — this is a read-only check.

---

## Self-Review notes (for the planner; not execution steps)

- **Spec coverage:** full-scene replacement (Task 4) ✓; line-art SVG in palette (Task 1) ✓; gentle sway via built-in Animated (Task 2) ✓; reduce-motion guard (Task 2) ✓; playful desert copy (Task 3) ✓; drop demo (Task 4) ✓; component-per-concern `tumbleweed.tsx`+`empty-state.tsx` (Tasks 1-3) ✓; remove orphaned style (Task 5) ✓; typecheck + manual verification (Tasks + Task 6) ✓.
- **No invented jest tests** — verification is typecheck + manual, matching the repo's actual tooling.
- **Type consistency:** `Tumbleweed({ size })`, `EmptyCaptures({ onOpenPaste })`, `PrimaryButton({ label, onPress, compact })` match real signatures confirmed in the codebase.
