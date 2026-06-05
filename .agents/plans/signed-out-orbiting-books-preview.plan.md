# Plan: Signed-Out Orbiting Books Product Preview

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the signed-out lower preview with a calm central Reel card surrounded by 3-5 book covers, subtly showing books being extracted from the Reel.

**Architecture:** Keep the signed-out screen order and auth behavior unchanged, and rebuild only the signed-out-only product preview component plus its local styles/assets. Use React Native `Animated` for native transform-only motion, respect reduced motion, and avoid adding GSAP, Remotion, or other dependencies to the Expo app.

**Tech Stack:** Expo React Native, TypeScript, React Native `Animated`, local PNG assets, pytest source regressions, Expo Web visual smoke checks.

---

## Summary

The current signed-out page copy and Google CTA are in the right direction, but the lower preview still reads as a linear "source to two cards" diagram. The requested direction is closer to the reference image: one believable portrait Reel in the center, several book covers arranged around it, and restrained orbital movement that communicates "Mentioned finds the books inside the Reel."

The implementation should not touch signed-in home/detail screens, backend code, Supabase, extraction flows, or auth behavior. It should replace only `SignedOutProductPreview`, its auth-preview styles, and the local preview asset needed for the new central Reel.

## Request Parse

- Problem: The current lower preview is too diagrammatic and does not match the premium onboarding reference.
- User story: As a signed-out user, I should immediately understand that I share a Reel and Mentioned extracts/saves the books mentioned inside it.
- Scope:
  - Signed-out auth page lower preview only.
  - Central portrait Reel card.
  - Four book covers around the Reel, with layout supporting three to five if adjusted later.
  - Subtle transform-only movement that can be disabled for reduced motion.
  - Local asset references under `mobile/assets/`.
- Out of scope:
  - Signed-in UI changes.
  - Auth, Supabase, backend, extraction, routing, or database changes.
  - Adding GSAP, Remotion, Reanimated, Skia, or new animation dependencies to the app.
  - App Store metadata or screenshots.
- Risk level: low to medium. It is visually scoped, but there is risk around small-screen clipping, distracting motion, and introducing a generated asset that feels less native than the current screen.

## Skill Guidance Applied

| Skill | Decision |
|------|----------|
| `emil-design-eng` | Animate only because this is rare onboarding and the motion explains the product. Keep it subtle, transform-only, and reduced-motion safe. Avoid "cool for cool's sake." |
| `hyperframes:gsap` | Use GSAP thinking for sequencing if prototyping in HTML/HyperFrames, but do not import GSAP into React Native. Map timeline/stagger concepts to RN `Animated.sequence`, `Animated.loop`, and per-book phase offsets. |
| `remotion:remotion-best-practices` | Remotion is useful only if creating a marketing/video proof later. This app change is not Remotion code, so validation is `npm run typecheck`, pytest, and in-app browser/mobile viewport checks, not Remotion Studio. |
| `mobile-app` | Stay inside `mobile/`, preserve Supabase auth behavior, inspect `mobile/package.json`, and validate with the existing typecheck command. |

## Motion Decision

| Question | Answer |
|----------|--------|
| Should this animate? | Yes, because users see it on the signed-out/onboarding screen, not during repeated daily workflows. |
| Purpose | Explanation: books visually emerge from and orbit around the Reel source. |
| Style | Slow, quiet drift along short orbital arcs. No full carousel spin, bounce, or loud shopping-like energy. |
| Properties | Animate only `transform` and maybe `opacity`; no `width`, `height`, `top`, `left`, padding, or layout values. |
| Timing | Per-book loops around 7-10 seconds, phase-offset by index. CTA press feedback remains the existing fast `pressed` state. |
| Reduced motion | Render the final static composition with all books visible and no transform animation. |

## Patterns To Follow

| Area | Source | Pattern |
|------|--------|---------|
| Signed-out layout | `mobile/src/screens/signed-out-screen.tsx` | Keep mark, headline, body, pending-source message, error, Google CTA, preview, and footer order unchanged. |
| Current preview isolation | `mobile/src/components/signed-out-product-preview.tsx` | Signed-out preview is already isolated from shared product preview components. Continue using a dedicated component. |
| Style ownership | `mobile/src/styles.ts` | Auth screen styles live in one shared StyleSheet; add/replace `authOrbit*` styles near the current `authProductPreview` block. |
| App mark asset | `mobile/src/components/ui.tsx` and `mobile/assets/app-mark.png` | Use local image assets through `require(...)`; do not reference temporary files. |
| Existing animation utility | `mobile/src/components/motion.tsx` | Existing animations use React Native `Animated`, `useNativeDriver: true`, and cleanup on unmount. Mirror that style rather than adding dependencies. |
| Test style | `tests/test_mobile_signed_out_screen.py` | Existing mobile checks are source-level pytest assertions for release-critical auth behavior. Add narrow source checks for reduced-motion/native animation and asset presence. |

## Files To Change

| File | Action | Purpose |
|------|--------|---------|
| `tests/test_mobile_signed_out_screen.py` | UPDATE | Add source regressions for the new preview asset and reduced-motion-safe native animation. |
| `mobile/assets/auth-orbit-reel-preview.png` | CREATE | New central Reel image without the large overlaid text in the current asset. |
| `mobile/src/components/signed-out-product-preview.tsx` | UPDATE | Replace connector/book-stack diagram with central Reel, orbit guides, and four book cover cards. |
| `mobile/src/styles.ts` | UPDATE | Replace old auth connector/book-stack styles with responsive orbit scene, Reel card, book cover, and guide-line styles. |

## Task 1: Add Preview Regression Checks

**Files:**
- Modify: `tests/test_mobile_signed_out_screen.py`

- [ ] **Step 1: Add preview file constants**

  Add these constants near the existing path constants:

  ```python
  SIGNED_OUT_PREVIEW = (
      REPO_ROOT / "mobile" / "src" / "components" / "signed-out-product-preview.tsx"
  )
  AUTH_ORBIT_REEL_PREVIEW = (
      REPO_ROOT / "mobile" / "assets" / "auth-orbit-reel-preview.png"
  )
  ```

- [ ] **Step 2: Add a narrow source-level regression**

  Add this test at the end of the file:

  ```python
  def test_signed_out_preview_uses_native_reduced_motion_safe_orbit() -> None:
      preview_source = SIGNED_OUT_PREVIEW.read_text()

      assert AUTH_ORBIT_REEL_PREVIEW.exists()
      assert "AccessibilityInfo.isReduceMotionEnabled()" in preview_source
      assert "reduceMotionChanged" in preview_source
      assert "Animated.loop" in preview_source
      assert "useNativeDriver: true" in preview_source
      assert "authOrbitBook" in preview_source
      assert "authPreviewConnector" not in preview_source
      assert "gsap" not in preview_source.lower()
      assert "remotion" not in preview_source.lower()
  ```

- [ ] **Step 3: Run the targeted pytest and verify failure**

  ```bash
  pytest tests/test_mobile_signed_out_screen.py::test_signed_out_preview_uses_native_reduced_motion_safe_orbit -q
  ```

  Expected: FAIL because `auth-orbit-reel-preview.png` and the reduced-motion-aware orbit component do not exist yet.

## Task 2: Create the Central Reel Asset

**Files:**
- Create: `mobile/assets/auth-orbit-reel-preview.png`

- [ ] **Step 1: Generate a clean portrait Reel image**

  Use `imagegen` during implementation with this prompt:

  ```text
  A realistic vertical smartphone Reel still for a premium mobile app onboarding screen. A young adult woman sits in a warm library cafe reading an open book, soft natural window light, bookshelves in the background, calm editorial photography, shallow depth of field, muted cream and deep green palette, no text, no subtitles, no logos, no watermark, no UI, 9:16 crop.
  ```

- [ ] **Step 2: Save the accepted asset locally**

  Save the final PNG to:

  ```text
  mobile/assets/auth-orbit-reel-preview.png
  ```

  The asset should be portrait-oriented and readable when displayed around 124-150 px wide. If the first generated image contains text artifacts, distorted hands, or a non-book object, regenerate before using it.

- [ ] **Step 3: Verify asset path and dimensions**

  ```bash
  file mobile/assets/auth-orbit-reel-preview.png
  sips -g pixelWidth -g pixelHeight mobile/assets/auth-orbit-reel-preview.png
  ```

  Expected: PNG image with portrait dimensions. Exact dimensions can vary, but width should be at least 600 px and height should be at least 1000 px.

## Task 3: Rebuild `SignedOutProductPreview`

**Files:**
- Modify: `mobile/src/components/signed-out-product-preview.tsx`

- [ ] **Step 1: Replace imports and asset require**

  Use React hooks, `AccessibilityInfo`, `Animated`, and `Easing` from React Native:

  ```tsx
  import { useEffect, useRef, useState } from 'react';
  import { AccessibilityInfo, Animated, Easing, Image, Text, useWindowDimensions, View } from 'react-native';

  import { styles } from '@/styles';

  const authOrbitReelPreview = require('../../assets/auth-orbit-reel-preview.png');
  ```

- [ ] **Step 2: Add book metadata**

  Replace the old two-item `previewBooks` array with four book covers:

  ```tsx
  const orbitBooks = [
    {
      title: 'Atomic\nHabits',
      author: 'James Clear',
      tone: 'paper',
      coverStyle: styles.authOrbitBookCoverPaper,
      positionStyle: styles.authOrbitBookUpperLeft,
      compactPositionStyle: styles.authOrbitBookUpperLeftCompact,
      driftX: 6,
      driftY: -5,
      rotateFrom: '-7deg',
      rotateTo: '-3deg',
    },
    {
      title: 'Deep\nWork',
      author: 'Cal Newport',
      tone: 'green',
      coverStyle: styles.authOrbitBookCoverGreen,
      positionStyle: styles.authOrbitBookUpperRight,
      compactPositionStyle: styles.authOrbitBookUpperRightCompact,
      driftX: -5,
      driftY: -4,
      rotateFrom: '6deg',
      rotateTo: '10deg',
    },
    {
      title: 'The Talent\nCode',
      author: 'Daniel Coyle',
      tone: 'olive',
      coverStyle: styles.authOrbitBookCoverOlive,
      positionStyle: styles.authOrbitBookLowerLeft,
      compactPositionStyle: styles.authOrbitBookLowerLeftCompact,
      driftX: 5,
      driftY: 5,
      rotateFrom: '-10deg',
      rotateTo: '-6deg',
    },
    {
      title: 'The\nShallows',
      author: 'Nicholas Carr',
      tone: 'cream',
      coverStyle: styles.authOrbitBookCoverCream,
      positionStyle: styles.authOrbitBookLowerRight,
      compactPositionStyle: styles.authOrbitBookLowerRightCompact,
      driftX: -6,
      driftY: 5,
      rotateFrom: '8deg',
      rotateTo: '4deg',
    },
  ] as const;
  ```

- [ ] **Step 3: Add reduced-motion state and animation values**

  Inside `SignedOutProductPreview`, add:

  ```tsx
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
  ```

- [ ] **Step 4: Add transform-only loop setup**

  Add a second effect after the reduced-motion effect:

  ```tsx
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
  ```

- [ ] **Step 5: Render the orbit scene**

  Replace the old return body with:

  ```tsx
  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={[styles.authProductPreview, isCompact && styles.authProductPreviewCompact]}
    >
      <View style={[styles.authOrbitGuide, styles.authOrbitGuideOuter]} />
      <View style={[styles.authOrbitGuide, styles.authOrbitGuideInner]} />

      <View style={[styles.authPreviewReelShell, isCompact && styles.authPreviewReelShellCompact]}>
        <Image source={authOrbitReelPreview} resizeMode="cover" style={styles.authPreviewReelImage} />
        <View style={styles.authPreviewReelMeta}>
          <Text style={styles.authPreviewReelPlay}>{'\u25B6'}</Text>
          <Text style={styles.authPreviewReelCount}>1.2M</Text>
        </View>
      </View>

      {orbitBooks.map((book, index) => {
        const animatedValue = orbitValues[index];
        const compactTransform = isCompact ? [{ scale: 0.88 }] : [];
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
        const isDarkCover = book.tone === 'green' || book.tone === 'olive';

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
            <View style={[styles.authOrbitBookCover, book.coverStyle]}>
              <Text
                numberOfLines={2}
                style={[styles.authOrbitBookTitle, isDarkCover && styles.authOrbitBookTextLight]}
              >
                {book.title}
              </Text>
              <View style={[styles.authOrbitBookRule, isDarkCover && styles.authOrbitBookRuleLight]} />
              <Text
                numberOfLines={1}
                style={[styles.authOrbitBookAuthor, isDarkCover && styles.authOrbitBookTextLight]}
              >
                {book.author}
              </Text>
            </View>
          </Animated.View>
        );
      })}
    </View>
  );
  ```

- [ ] **Step 6: Run typecheck and fix TypeScript issues**

  ```bash
  cd mobile && npm run typecheck
  ```

  Expected after style additions in Task 4: PASS. If run before Task 4, expect missing style keys.

## Task 4: Replace Auth Preview Styles

**Files:**
- Modify: `mobile/src/styles.ts`

- [ ] **Step 1: Replace the old auth preview layout block**

  Replace `authProductPreview` through `authPreviewBookAuthor` with orbit-scene styles. Keep `authPreviewWrap` and all non-auth product preview styles unchanged.

- [ ] **Step 2: Use fixed scene dimensions with compact variants**

  Implement these dimensions:

  ```ts
  authProductPreview: {
    alignItems: 'center',
    alignSelf: 'center',
    height: 336,
    justifyContent: 'center',
    maxWidth: 352,
    overflow: 'visible',
    position: 'relative',
    width: '100%',
  },
  authProductPreviewCompact: {
    height: 296,
    maxWidth: 278,
  },
  authPreviewReelShell: {
    aspectRatio: 0.56,
    backgroundColor: colors.ink,
    borderColor: 'rgba(16, 26, 23, 0.20)',
    borderRadius: radius.lg,
    borderWidth: 1,
    boxShadow: '0 16px 30px rgba(16, 26, 23, 0.18)',
    overflow: 'hidden',
    width: 142,
    zIndex: 3,
  },
  authPreviewReelShellCompact: {
    borderRadius: radius.md,
    width: 116,
  },
  authPreviewReelImage: {
    height: '100%',
    width: '100%',
  },
  authPreviewReelMeta: {
    alignItems: 'center',
    bottom: spacing.sm,
    flexDirection: 'row',
    gap: spacing.xs,
    left: spacing.sm,
    position: 'absolute',
  },
  authPreviewReelPlay: {
    color: colors.onPrimary,
    fontSize: 14,
    fontWeight: '700',
    lineHeight: 16,
  },
  authPreviewReelCount: {
    color: colors.onPrimary,
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 0,
    lineHeight: 16,
  },
  ```

- [ ] **Step 3: Add orbit guide styles**

  Add restrained elliptical guide lines:

  ```ts
  authOrbitGuide: {
    borderColor: 'rgba(14, 111, 104, 0.22)',
    borderRadius: 999,
    borderWidth: 1,
    position: 'absolute',
  },
  authOrbitGuideOuter: {
    height: 212,
    transform: [{ rotate: '-10deg' }],
    width: 336,
  },
  authOrbitGuideInner: {
    height: 176,
    opacity: 0.6,
    transform: [{ rotate: '14deg' }],
    width: 282,
  },
  ```

- [ ] **Step 4: Add book positioning styles**

  Add four absolute-positioned anchors plus compact overrides:

  ```ts
  authOrbitBook: {
    position: 'absolute',
    zIndex: 4,
  },
  authOrbitBookUpperLeft: {
    left: 4,
    top: 24,
  },
  authOrbitBookUpperLeftCompact: {
    left: -4,
    top: 20,
  },
  authOrbitBookUpperRight: {
    right: 4,
    top: 42,
  },
  authOrbitBookUpperRightCompact: {
    right: -8,
    top: 36,
  },
  authOrbitBookLowerLeft: {
    bottom: 18,
    left: 8,
  },
  authOrbitBookLowerLeftCompact: {
    bottom: 18,
    left: -10,
  },
  authOrbitBookLowerRight: {
    bottom: 22,
    right: 8,
  },
  authOrbitBookLowerRightCompact: {
    bottom: 20,
    right: -10,
  },
  ```

  Compact scale should be composed in the component transform array, not in a separate style object, so animated transforms do not overwrite it.

- [ ] **Step 5: Add book cover styles**

  Add book cover visuals that read as covers, not shopping cards:

  ```ts
  authOrbitBookCover: {
    alignItems: 'center',
    borderColor: 'rgba(16, 26, 23, 0.12)',
    borderRadius: radius.sm,
    borderWidth: 1,
    boxShadow: '0 9px 18px rgba(16, 26, 23, 0.14)',
    height: 94,
    justifyContent: 'center',
    paddingHorizontal: spacing.xs,
    paddingVertical: spacing.sm,
    width: 66,
  },
  authOrbitBookCoverPaper: {
    backgroundColor: '#EEE7D8',
  },
  authOrbitBookCoverGreen: {
    backgroundColor: '#0F302D',
  },
  authOrbitBookCoverOlive: {
    backgroundColor: '#4D5840',
  },
  authOrbitBookCoverCream: {
    backgroundColor: '#F0E8D8',
  },
  authOrbitBookTitle: {
    color: colors.ink,
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 0,
    lineHeight: 13,
    textAlign: 'center',
  },
  authOrbitBookRule: {
    backgroundColor: 'rgba(16, 26, 23, 0.22)',
    height: 1,
    marginVertical: spacing.xs,
    width: 28,
  },
  authOrbitBookAuthor: {
    color: colors.inkMuted,
    fontSize: 8,
    fontWeight: '500',
    letterSpacing: 0,
    lineHeight: 10,
    textAlign: 'center',
  },
  ```

  For `green` and `olive` covers, add a conditional style in the component so title/rule/author use light text:

  ```tsx
  const isDarkCover = book.tone === 'green' || book.tone === 'olive';
  ```

  Then apply `styles.authOrbitBookTextLight` and `styles.authOrbitBookRuleLight`:

  ```ts
  authOrbitBookTextLight: {
    color: colors.onPrimary,
  },
  authOrbitBookRuleLight: {
    backgroundColor: 'rgba(255, 255, 255, 0.34)',
  },
  ```

- [ ] **Step 6: Run typecheck**

  ```bash
  cd mobile && npm run typecheck
  ```

  Expected: PASS.

## Task 5: Visual Polish Pass

**Files:**
- Modify: `mobile/src/components/signed-out-product-preview.tsx`
- Modify: `mobile/src/styles.ts`

- [ ] **Step 1: Check the full signed-out screen at standard width**

  Use the in-app browser or Playwright against the existing Expo web server at:

  ```text
  http://localhost:8082/
  ```

  Check a viewport around `393x852` or the current browser size `417x901`.

  Expected:
  - App mark, headline, body, Google CTA, and preview all fit cleanly.
  - Preview starts below the CTA with breathing room.
  - Central Reel is the visual anchor.
  - Book covers do not collide with the CTA, footer, Reel card, or screen edges.
  - Motion is subtle enough to read as polish, not distraction.

- [ ] **Step 2: Check the compact viewport**

  Check `320x568`.

  Expected:
  - No horizontal overflow.
  - CTA text remains readable.
  - Preview may be partially lower on the scroll view, but it should not clip awkwardly.
  - Book text remains legible enough, or dark/light contrast is adjusted.

- [ ] **Step 3: Adjust only local preview spacing**

  If visual checks fail, adjust only:
  - `authProductPreview` height/maxWidth.
  - Book anchor styles.
  - Reel width.
  - `authPreviewWrap` top padding if the preview crowds the CTA.

  Do not change auth copy, auth behavior, signed-in screens, or backend code.

## Task 6: Final Validation

**Files:**
- No additional files unless validation exposes a scoped issue.

- [ ] **Step 1: Run TypeScript validation**

  ```bash
  cd mobile && npm run typecheck
  ```

  Expected: PASS.

- [ ] **Step 2: Run signed-out source regressions**

  ```bash
  pytest tests/test_mobile_signed_out_screen.py -q
  ```

  Expected: PASS.

- [ ] **Step 3: Inspect git status**

  ```bash
  git status --short
  ```

  Expected: only the planned preview component, styles, test file, and local preview asset are changed for this task. Do not stage generated runtime artifacts, `.expo`, `dist`, `node_modules`, `app.db`, or `data/artifacts/`.

## Validation

```bash
cd mobile && npm run typecheck
pytest tests/test_mobile_signed_out_screen.py -q
```

Manual visual validation:

1. Open `http://localhost:8082/` in the in-app browser.
2. Inspect a standard mobile viewport around `393x852` or `417x901`.
3. Inspect `320x568`.
4. Confirm reduced motion by toggling OS/browser reduced motion if available, or by temporarily forcing `shouldReduceMotion` to `true` during local visual validation and then reverting that temporary edit.

## Acceptance Criteria

- [ ] Signed-out headline/body/Google CTA/auth behavior are unchanged.
- [ ] Lower preview shows one central portrait Reel and four surrounding book covers.
- [ ] The composition communicates books extracted from a Reel without connector-arrow diagramming.
- [ ] Motion uses React Native `Animated`, `useNativeDriver: true`, transform-only values, and cleanup on unmount.
- [ ] Reduced motion disables the loop and leaves a polished static composition.
- [ ] No GSAP, Remotion, Reanimated, Skia, or new dependencies are added to the Expo app.
- [ ] The screen has no horizontal overflow at `320x568`.
- [ ] `cd mobile && npm run typecheck` passes.
- [ ] `pytest tests/test_mobile_signed_out_screen.py -q` passes.
- [ ] Generated/runtime artifacts are not staged.

## Main Risks

- The generated central image can undermine the premium feel if it contains text artifacts, odd hands, or a stock-photo look. Regenerate until it reads as a believable Reel still.
- Absolute-positioned book covers can clip or collide on 320 px wide screens. Validate compact styles early instead of tuning only at the default browser width.
- A literal fast orbit would feel gimmicky. Keep the movement as a slow drift along short arcs; the static arrangement should already explain the product.
- React Native style arrays with animated transforms can overwrite compact scale transforms. Compose compact scale inside the rendered transform array when needed.
