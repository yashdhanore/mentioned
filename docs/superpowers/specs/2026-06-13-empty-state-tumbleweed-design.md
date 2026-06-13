# Empty-state tumbleweed — design

**Date:** 2026-06-13
**Area:** `mobile/` — home screen empty state
**Status:** Approved (design); implementation not started

## Problem

When a signed-in user has no saved posts, the home screen renders the
`EmptyCaptures` card (title + explanatory text + a `SourceToBooksPreview` demo +
a Paste-link button). On a tall device this leaves a large empty beige void
below the card, which reads as broken/unfinished. We want the empty state to
feel intentional and charming — a rolling-desert "looks empty here" metaphor.

## Decisions

- **Replace the whole empty card** with a single full-scene empty state. The
  bordered card box and the `SourceToBooksPreview` demo are dropped. The subline
  copy carries the product explanation instead.
- **Tumbleweed art:** custom on-brand line-art **SVG** (react-native-svg, already
  a dependency) in the app's sage/green palette. No emoji, no photo.
- **Motion:** gentle **idle sway** — the weed rests and rotates/nudges slightly
  in place, as if nudged by wind. No rolling-across, no loop-travel.
- **Accessibility:** respect reduce-motion — render the weed static when the OS
  reduce-motion setting is on. Scene and copy stay; only movement is removed.
- **Copy (playful desert):**
  - Headline: `Sure looks empty out here`
  - Subline: `Share a reel and Mentioned will round up the books mentioned inside.`

## Architecture (Approach A — component-per-concern)

Two new components, mirroring the existing structure (`product-preview.tsx`,
`motion.tsx`):

### `mobile/src/components/tumbleweed.tsx`
- Default-exports a `Tumbleweed` component that draws the weed as an SVG and
  owns its own sway animation.
- **Drawing:** a tangled ball built from 3–4 overlapping elliptical stroke paths
  (`Path`/`Ellipse`) at slight, differing rotations so it reads as an organic
  weed rather than a clean ring. Stroke `colors.secondary` (#4E5D57), ~1.5px, no
  fill. Default rendered size ~96px (accept a `size` prop with that default).
- **Ground shadow:** a low-opacity flat ellipse beneath the weed
  (`colors.ink` at ~0.06 opacity). **Static** — it does not animate; only the
  weed sways above it.
- **Sway animation:** one `Animated.Value` driven by RN's built-in `Animated`
  API (same approach as `motion.tsx`). A looping `Animated.sequence` /
  `Animated.loop` interpolated into a small `rotate` (≈ −4° → +4°) plus a
  ~1–2px `translateX`. `useNativeDriver: true`. ~2.0–2.4s ease-in-out per half
  cycle so it breathes rather than ticks. Animation is started in `useEffect`
  and stopped on unmount.
- **Reduce-motion guard:** read `AccessibilityInfo.isReduceMotionEnabled()` on
  mount and subscribe to its change event. When reduce-motion is enabled, skip
  starting the loop and render the weed at its neutral resting transform.

### `mobile/src/components/empty-state.tsx`
- Exports `EmptyCaptures` (moved out of `home-screen.tsx`) — or a new
  `TumbleweedEmpty` that `home-screen.tsx` renders. Composes: `<Tumbleweed />`,
  the headline, the subline, and the existing `PrimaryButton` (compact) wired to
  the `onOpenPaste` callback. The whole scene is wrapped in the existing
  `FadeInView` so it eases in on mount.
- Layout: vertically centered column, centered text, generous vertical spacing
  using existing `spacing` tokens. No bordered-card container (the card box is
  intentionally removed).

### `mobile/src/screens/home-screen.tsx`
- The existing inline `EmptyCaptures` (lines ~131–144) is removed; the
  `!isLoading && captures.length === 0` branch renders the new empty-state
  component, passing `onOpenPaste`.
- Remove the now-unused `SourceToBooksPreview` import **only if** it has no other
  consumer in this file. (`signed-out-product-preview.tsx` is a separate
  component for the signed-out screen and is out of scope.)

### Styles (`mobile/src/styles.ts`)
- Add empty-scene styles (centered column, headline `typography.titleLg` /
  `colors.onSurface`, subline `typography.bodySm` / `colors.onMuted` centered,
  spacing). Reuse existing tokens; do not introduce new color values beyond what
  `theme.ts` already defines.
- The old `emptyPreviewWrap` style may become unused — remove it if no other
  consumer remains.

## Data flow

No data or backend changes. Pure presentation. The empty branch is still gated by
`!isLoading && captures.length === 0` in `home-screen.tsx`. `onOpenPaste` is the
same callback already threaded into `EmptyCaptures`.

## Motion rationale (Emil framework)

- Empty state is a **rare** view, so ambient motion is earned (vs. high-frequency
  UI where animation should be removed).
- Sway uses **ease-in-out** (on-screen movement that reverses), kept slow and
  small so it reads as calm/breathing, matching Mentioned's quiet editorial mood.
- Only `transform` (rotate/translate) + the mount opacity fade are animated —
  hardware-accelerated via `useNativeDriver`.
- Reduce-motion removes movement but keeps the scene, per the "fewer and gentler,
  not zero" guidance.

## Testing / validation

- `cd mobile && npm run typecheck` must pass.
- Manual: sign in with an empty account (or temporarily force `captures.length
  === 0`) and confirm: scene centers, weed sways subtly, Paste link opens the
  paste sheet, scene fades in on mount.
- Reduce-motion: enable iOS Settings → Accessibility → Motion → Reduce Motion and
  confirm the weed renders static (no sway) while the scene still shows.

## Out of scope / non-goals

- No new animation library (no Reanimated/Lottie). Built-in `Animated` only.
- No change to the signed-out screen or its product preview.
- No rolling-across or looping-travel motion.
- No backend, data, or navigation changes.

## YAGNI notes

- Single shared `Animated.Value` for the sway; no per-twig animation.
- `Tumbleweed` takes only a `size` prop (default 96). No color/variant props
  until a second use site exists.
