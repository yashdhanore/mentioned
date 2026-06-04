---
version: beta
name: Mentioned
description: Consumer mobile app design system for saving recommendations mentioned inside social sources.
colors:
  primary: "#0E6F68"
  primary-pressed: "#094C48"
  primary-soft: "#DDF5F1"
  on-primary: "#FFFFFF"
  neutral: "#F7F5F0"
  neutral-deep: "#ECE7DD"
  surface: "#FFFFFF"
  surface-muted: "#F1EEE6"
  surface-elevated: "#FFFEFA"
  paper: "#F4EFE5"
  paper-edge: "#DCD4C6"
  ink: "#101A17"
  ink-muted: "#69706A"
  secondary: "#4E5D57"
  border: "#DDD7CC"
  hairline: "rgba(16,26,23,0.10)"
  book: "#2F4A44"
  book-soft: "#E7ECE5"
  source-context: "#405B55"
  source-context-soft: "#E9EDE7"
  warning: "#8A5E00"
  warning-soft: "#FFF3D6"
  success: "#17643C"
  success-soft: "#E5F6EA"
  error: "#B42318"
  error-soft: "#FDE7E4"
typography:
  display:
    fontFamily: "Satoshi, Geist, SF Pro Display, system-ui, sans-serif"
    fontSize: 44px
    fontWeight: 650
    lineHeight: 1.02
    letterSpacing: 0em
  headline-lg:
    fontFamily: "Satoshi, Geist, SF Pro Display, system-ui, sans-serif"
    fontSize: 34px
    fontWeight: 650
    lineHeight: 1.08
    letterSpacing: 0em
  headline-md:
    fontFamily: "Satoshi, Geist, SF Pro Display, system-ui, sans-serif"
    fontSize: 24px
    fontWeight: 650
    lineHeight: 1.16
    letterSpacing: 0em
  title-lg:
    fontFamily: "Satoshi, Geist, SF Pro Text, system-ui, sans-serif"
    fontSize: 20px
    fontWeight: 650
    lineHeight: 1.25
    letterSpacing: 0em
  title-md:
    fontFamily: "Satoshi, Geist, SF Pro Text, system-ui, sans-serif"
    fontSize: 17px
    fontWeight: 650
    lineHeight: 1.3
    letterSpacing: 0em
  body-md:
    fontFamily: "Satoshi, Geist, SF Pro Text, system-ui, sans-serif"
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: 0em
  body-sm:
    fontFamily: "Satoshi, Geist, SF Pro Text, system-ui, sans-serif"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.42
    letterSpacing: 0em
  label-lg:
    fontFamily: "Satoshi, Geist, SF Pro Text, system-ui, sans-serif"
    fontSize: 14px
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: 0em
  label-md:
    fontFamily: "Satoshi, Geist, SF Pro Text, system-ui, sans-serif"
    fontSize: 12px
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: 0em
  caption:
    fontFamily: "Satoshi, Geist, SF Pro Text, system-ui, sans-serif"
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.35
    letterSpacing: 0em
rounded:
  none: 0px
  xs: 4px
  sm: 6px
  md: 10px
  lg: 16px
  xl: 24px
  full: 9999px
spacing:
  2xs: 2px
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  2xl: 32px
  3xl: 44px
  screen-margin: 20px
  card-padding: 16px
  bottom-tab-height: 64px
components:
  screen:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    rounded: "{rounded.none}"
    padding: 20px
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-lg}"
    rounded: "{rounded.md}"
    padding: 16px
    height: 52px
  button-secondary:
    backgroundColor: "{colors.surface-muted}"
    textColor: "{colors.ink}"
    typography: "{typography.label-lg}"
    rounded: "{rounded.md}"
    padding: 14px
    height: 48px
  reel-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.lg}"
  book-row:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: 14px
  book-spine:
    backgroundColor: "{colors.book}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.sm}"
    width: 52px
    height: 74px
  source-context-card:
    backgroundColor: "{colors.source-context-soft}"
    textColor: "{colors.source-context}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: 14px
---

# Mentioned Design System

## 1. Visual Theme & Atmosphere

Mentioned is a consumer mobile app for saving recommendations that would otherwise disappear inside social video, newsletters, messages, and travel content. The first supported category is books. The product language must still be flexible enough to later say: "Don't lose the places that were mentioned", "Don't lose the essays that were mentioned", or "Don't lose the restaurants that were mentioned."

The interface should feel like a quiet personal archive: editorial reading culture, social-source immediacy, and native mobile utility. It should not feel like a marketing landing page, admin dashboard, AI audit screen, or generic social clone.

Atmosphere:

- **Density:** Daily App Balanced, 4/10. Screens should be useful and scannable, but not crowded.
- **Variance:** Offset Asymmetric, 7/10. Use controlled asymmetry, featured tiles, and source-to-result compositions rather than uniform card rows.
- **Motion:** Fluid Native, 5/10. Use short tactile feedback, skeleton shimmer, and staggered arrivals only where they explain state.

Core product promise:

> Don't lose the books that were mentioned.

The active noun is **books** in v1. Treat it as a semantic slot, not hardcoded brand positioning. Future nouns can rotate in onboarding and empty states, but production v1 remains book-first.

## 2. Color Palette & Roles

Use one restrained teal accent and a paper-warm neutral system. Do not drift into purple, neon blue, beige monochrome, or heavy dark-mode styling.

- **Archive Canvas (#F7F5F0):** Primary app background. Warm enough to feel editorial, clean enough to avoid a beige theme.
- **Folded Paper (#F4EFE5):** Behind Reel previews, source quote blocks, and product-preview surfaces.
- **Paper Edge (#DCD4C6):** Soft physical edge color for source paper layers and subtle separators.
- **Pure Surface (#FFFFFF):** Book rows, sheets, inputs, and raised content.
- **Raised Surface (#FFFEFA):** Premium elevated shells and nested preview panels.
- **Charcoal Ink (#101A17):** Primary text. Never use pure black.
- **Muted Graphite (#69706A):** Secondary text, captions, source metadata.
- **Sage Line (#DDD7CC):** Structural borders and dividers.
- **Quiet Teal (#0E6F68):** The single accent for primary CTAs, active source actions, and the app mark.
- **Deep Teal (#094C48):** Pressed primary CTA and dark accent surfaces.
- **Book Green (#2F4A44):** Typographic book spines and book-first visual details.
- **Source Sage (#405B55):** Source snippets and Open source treatment.
- **Warning Amber (#8A5E00), Success Green (#17643C), Error Red (#B42318):** Use only for real state communication.

Primary teal must never flood the interface. Most pixels should be canvas, paper, image, ink, and white surface.

## 3. Typography Rules

Use a premium geometric sans direction: Satoshi, Geist, or Cabinet Grotesk when installed. Until custom fonts are wired into Expo, native SF on iOS is acceptable. Do not document or add Inter as a fallback.

- **Display:** Controlled large type for signed-out and empty-state concepts. Use 40-46px on mobile, line-height near 1.02, and no negative letter spacing.
- **Screen headlines:** 30-34px, 2 lines maximum in normal screens.
- **Section titles:** 20-24px, compact and clear.
- **Body:** 14-16px, relaxed leading, max 65 characters where possible.
- **Labels and metadata:** 12-14px, medium weight. Use tabular numbers for timestamps and counts when implemented.

Avoid fake editorial serif styling in the app shell. Mentioned is a native utility with an editorial texture, not a magazine site.

## 4. Layout Principles

Mentioned is mobile-first. Screens must respect safe areas and keep primary actions within comfortable thumb reach.

Use these screen patterns:

- **Signed out:** Asymmetric onboarding with the headline, one primary CTA, and a miniature source-to-books product preview. Do not use onboarding carousels, badges, or feature lists.
- **Saved Reels home:** A two-column visual collection with one subtly featured latest tile when content exists. Tiles are browsable source memories, not equal marketing cards.
- **Reel detail:** Ready screens are books-first: compact navigation, a small source memory strip, Books mentioned, then the richer Original source module with preview/context and Open on Instagram. Processing, failed, and no-books screens keep their state content near the top and leave source reopening secondary but reachable.
- **Books mentioned:** Compact editorial rows with typographic spines. Do not use chevrons unless a row navigates or expands.
- **States:** Loading uses skeletons. Empty uses a composed source-to-result preview. Failed and no-books states remain calm and recoverable.

Do not introduce a bottom tab bar in v1. Profile/settings and manual paste stay as lightweight sheets or top-right actions.

## 5. Component Stylings

**Buttons:** Primary buttons are deep teal, 52px tall, and have tactile press feedback (`scale: 0.97` to `0.98`). Do not add neon shadows. Secondary buttons use paper or white surfaces with sage borders.

**Icon buttons:** Use precise line icons or native glyph-like symbols. Avoid raw text such as `+`, `...`, or profile initials as the final visual language when an icon is clearer.

**Reel tiles:** Use real or generic source thumbnails with a subtle bottom scrim. Normal ready tiles should be visually quiet. Processing and attention states use small icon-only indicators.

**Featured tile:** The newest or most relevant source may be slightly taller or wider in the home grid. This creates collection rhythm without turning the screen into a feed.

**Book rows:** Use a typographic spine/cover placeholder, title, author, and concise synopsis. Prefer hairline dividers and soft surfaces over bulky cards.

**Source quote:** Render cleaned source context as a quote or source block with a left accent line. Never render backend evidence, raw transcript debris, confidence, provider names, or artifact paths.

**Sheets:** Bottom sheets use a soft raised surface, a centered handle, and grouped rows. Destructive actions remain secondary and confirmed.

## 6. Motion & Interaction

Use motion only where it supports comprehension or tactile feedback.

- Button and tile press: 100-160ms scale feedback.
- Sheet entrance: native slide is acceptable; future custom motion should use a spring-like curve.
- New book rows: stagger by 30-60ms when a processing state resolves.
- Loading: skeleton shimmer matching final row dimensions; no generic circular spinner for primary loading states.
- Status dots: subtle pulse only for active processing, not for static ready content.

Never animate layout properties. Use transform and opacity. Do not add decorative perpetual motion to content users scan repeatedly.

## 7. Content Rules

Use concrete product copy:

- Signed out headline: **Don't lose the books that were mentioned.**
- Supporting copy: **Share a Reel, keep the source, find it later.**
- Processing: **Finding books...**
- Home title: **Saved Reels**
- Detail section: **Books mentioned**

Avoid AI/marketing filler such as "elevate", "seamless", "unlock", "supercharge", and "next-gen". Avoid generic placeholder names and exact third-party social chrome. Do not use celebrities or recognizable creators in production mock data.

## 8. Anti-Patterns

Never do these in Mentioned:

- No emojis in app UI, docs, labels, or alt text.
- No Inter fallback in design docs or token files.
- No pure black (`#000000`).
- No purple/neon AI gradients or glowing buttons.
- No fake realistic book covers that imply rights or metadata.
- No copied Instagram/TikTok UI, logos, verification badges, or brand colors.
- No chevrons on non-interactive book rows.
- No giant marketing hero inside the signed-in app.
- No bottom tab bar until there are real first-class destinations.
- No confidence scores, model stages, raw evidence, provider names, artifacts, or worker internals in user-facing UI.
- No generic 3-card feature rows.
- No decorative elements that overlap text or reduce tap clarity.
