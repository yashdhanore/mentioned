---
version: alpha
name: Mentioned
description: Consumer mobile app design system for capturing book recommendations from shared social reels.
colors:
  primary: "#0E6F68"
  primary-pressed: "#0A4F4A"
  primary-soft: "#DDF5F1"
  on-primary: "#FFFFFF"
  secondary: "#53615B"
  tertiary: "#345D8C"
  neutral: "#F6F8F5"
  surface: "#FFFFFF"
  surface-muted: "#EEF3EF"
  surface-elevated: "#FCFDFB"
  on-surface: "#14201B"
  on-muted: "#64706A"
  border: "#DDE5DF"
  book: "#345D8C"
  book-soft: "#E7F0FA"
  source-context: "#4B6378"
  source-context-soft: "#EAF0F4"
  warning: "#8A5E00"
  warning-soft: "#FFF3D6"
  success: "#17643C"
  success-soft: "#E5F6EA"
  error: "#B42318"
  error-soft: "#FDE7E4"
typography:
  headline-lg:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter', sans-serif"
    fontSize: 30px
    fontWeight: 700
    lineHeight: 1.14
    letterSpacing: 0em
  headline-md:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter', sans-serif"
    fontSize: 24px
    fontWeight: 700
    lineHeight: 1.18
    letterSpacing: 0em
  title-lg:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', sans-serif"
    fontSize: 20px
    fontWeight: 650
    lineHeight: 1.25
    letterSpacing: 0em
  title-md:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', sans-serif"
    fontSize: 17px
    fontWeight: 650
    lineHeight: 1.3
    letterSpacing: 0em
  body-lg:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', sans-serif"
    fontSize: 17px
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: 0em
  body-md:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', sans-serif"
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: 0em
  body-sm:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', sans-serif"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: 0em
  label-lg:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', sans-serif"
    fontSize: 14px
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: 0em
  label-md:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', sans-serif"
    fontSize: 12px
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: 0em
  caption:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', sans-serif"
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.35
    letterSpacing: 0em
rounded:
  none: 0px
  xs: 4px
  sm: 6px
  md: 8px
  lg: 12px
  full: 9999px
spacing:
  2xs: 2px
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  2xl: 32px
  screen-margin: 20px
  card-padding: 14px
  bottom-tab-height: 64px
components:
  screen:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-md}"
    rounded: "{rounded.none}"
    padding: 20px
  bottom-tab:
    backgroundColor: "{colors.surface-elevated}"
    textColor: "{colors.on-muted}"
    typography: "{typography.label-md}"
    rounded: "{rounded.none}"
    height: 64px
  divider:
    backgroundColor: "{colors.border}"
    textColor: "{colors.secondary}"
    typography: "{typography.caption}"
    rounded: "{rounded.none}"
    height: 1px
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-lg}"
    rounded: "{rounded.md}"
    padding: 14px
    height: 48px
  button-primary-pressed:
    backgroundColor: "{colors.primary-pressed}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-lg}"
    rounded: "{rounded.md}"
    padding: 14px
    height: 48px
  button-secondary:
    backgroundColor: "{colors.surface-muted}"
    textColor: "{colors.on-surface}"
    typography: "{typography.label-lg}"
    rounded: "{rounded.md}"
    padding: 14px
    height: 48px
  button-destructive:
    backgroundColor: "{colors.error-soft}"
    textColor: "{colors.error}"
    typography: "{typography.label-lg}"
    rounded: "{rounded.md}"
    padding: 14px
    height: 48px
  input:
    backgroundColor: "{colors.surface-muted}"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: 14px
    height: 48px
  chip:
    backgroundColor: "{colors.surface-muted}"
    textColor: "{colors.secondary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.full}"
    padding: 10px
  chip-selected:
    backgroundColor: "{colors.primary-soft}"
    textColor: "{colors.primary-pressed}"
    typography: "{typography.label-md}"
    rounded: "{rounded.full}"
    padding: 10px
  book-chip:
    backgroundColor: "{colors.book-soft}"
    textColor: "{colors.tertiary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.full}"
    padding: 10px
  book-cover-placeholder:
    backgroundColor: "{colors.book}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.sm}"
    width: 44px
    height: 64px
  status-attention:
    backgroundColor: "{colors.warning-soft}"
    textColor: "{colors.warning}"
    typography: "{typography.label-md}"
    rounded: "{rounded.full}"
    padding: 8px
  status-complete:
    backgroundColor: "{colors.success-soft}"
    textColor: "{colors.success}"
    typography: "{typography.label-md}"
    rounded: "{rounded.full}"
    padding: 8px
  reel-status-ready:
    backgroundColor: "{colors.success-soft}"
    textColor: "{colors.success}"
    typography: "{typography.caption}"
    rounded: "{rounded.full}"
    width: 18px
    height: 18px
  reel-status-processing:
    backgroundColor: "{colors.warning-soft}"
    textColor: "{colors.warning}"
    typography: "{typography.caption}"
    rounded: "{rounded.full}"
    width: 18px
    height: 18px
  reel-status-attention:
    backgroundColor: "{colors.error-soft}"
    textColor: "{colors.error}"
    typography: "{typography.caption}"
    rounded: "{rounded.full}"
    width: 18px
    height: 18px
  book-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: 14px
  source-context-card:
    backgroundColor: "{colors.source-context-soft}"
    textColor: "{colors.source-context}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: 14px
---

# Mentioned Design System

## Overview

Mentioned is a consumer mobile app for readers who discover books inside social videos. The core product moment is simple: a user sees a Reel, taps share, sends it to Mentioned, and the Reel appears in a saved collection with the books mentioned inside it.

The interface should feel like a fast personal utility, not an admin dashboard, social feed, or marketing page. It should be calm, native, trustworthy, and lightly bookish without looking old-fashioned. The product personality is precise and helpful: it captures recommendations without asking the user to rewatch, transcribe, or manually organize everything.

The design must hide extraction mechanics from normal users. Auto-saved books should feel like the natural result of opening a saved Reel, not like a model audit screen. Backend confidence, raw evidence, stages, artifacts, and worker terms must stay out of the primary UI.

The v1 information architecture is Reel-first. Home is a two-column visual collection of saved Reels/posts, mostly represented by thumbnails. Tapping a saved Reel opens a detail screen with the Reel video or thumbnail at the top and the books mentioned below. A global book library is deferred until the product proves that users want cross-Reel browsing.

After a user shares a Reel to Mentioned, the app should open directly to that new Reel detail page in a processing state. Do not drop the user into the home grid and make them find the newly shared Reel. The home grid is for later browsing and returning to saved sources.

## Colors

The palette uses warm neutral surfaces, high-contrast charcoal text, and one restrained teal action color.

- **Primary (#0E6F68):** Used for the most important action on a screen, such as Find books, Continue, Retry, or Save changes.
- **Primary Soft (#DDF5F1):** Used for selected filters, subtle active states, and quiet successful surfaces.
- **Neutral (#F6F8F5):** The app background. It should read as clean and personal, softer than pure white but not beige.
- **Surface (#FFFFFF):** Cards, sheets, and list rows.
- **Surface Muted (#EEF3EF):** Inputs, inactive chips, bottom tab backgrounds, and secondary controls.
- **Book (#345D8C):** A supporting accent for book category labels and book-focused visual details.
- **Source Context (#4B6378):** Used for source creator, caption snippets, and Open source areas, not as a visible debug concept.
- **Warning (#8A5E00):** Used only for failed, empty, or needs-attention states.
- **Success (#17643C):** Used for completed or successful states when a visible state is necessary.
- **Error (#B42318):** Used for destructive actions and failed extraction states.

Primary teal should not dominate the screen. Most UI should be neutral, with color reserved for actions, source state, and category recognition.

## Typography

Use the native iOS system stack first, with Inter as a cross-platform fallback. The typography should feel compact, readable, and app-native.

- **Headlines:** Use `headline-lg` and `headline-md` for screen titles such as Saved, Books mentioned, and Reel detail. Keep them short and avoid landing-page scale.
- **Titles:** Use `title-lg` and `title-md` for book titles, detail headers, and sheet titles.
- **Body:** Use `body-md` for normal descriptions and source context. Use `body-sm` and `caption` for source creator, status metadata, and timestamps.
- **Labels:** Use `label-lg` for buttons and `label-md` for chips, tabs, source labels, and status badges.

Do not scale type based on viewport width. Do not use negative letter spacing. Long book titles must wrap gracefully rather than shrink into illegible text.

## Layout

Mentioned is mobile-first. Screens should respect iOS safe areas, use a strict 8px-based rhythm, and keep primary actions within thumb reach.

The default app shell should keep the primary collection first. V1 should not use a bottom tab bar. Use a simple top navigation treatment instead: small Mentioned brand on the left and profile/settings plus a secondary paste-link action on the right. Capture happens mostly through the share sheet, not through a persistent tab.

Core screen structure:

- **Share extension:** Compact iOS-style share target that clearly says Share to Mentioned without copying a third-party social app's exact UI.
- **Incoming link:** Show source creator, normalized source URL, and a single Find books action.
- **Finding books:** After share handoff, open the new Reel detail screen and show a calm processing state below the Reel preview. Prefer user-facing copy such as “Finding books…” over backend progress labels.
- **Saved Reels home:** Show saved Reel/post thumbnails in a two-column grid. Each tile should show only the thumbnail and a tiny creator handle when available. Do not show book counts, captions, descriptions, or status text on normal tiles.
- **Reel detail:** Show a large but not edge-to-edge vertical Reel preview near the top, source creator, caption snippet, and books mentioned. The Reel preview should confirm the tapped source without turning the app into a full-screen video player.
- **Books mentioned:** On the Reel detail screen, show extracted books inline as mobile rows/cards with cover placeholder, title, author, and short synopsis. Do not show saved badges, confidence, evidence, review status, edit controls, or remove controls. Do not require a separate book detail screen in v1.
- **Book saving later:** In a later version, each book row may expose a small plus action so users can save a book to their personal book library. This is separate from the v1 saved-Reel collection.

Use cards only for repeated items such as books and source rows. Do not put cards inside cards. Full-screen sections should be unframed layouts, sheets, or simple lists.

## Elevation & Depth

Depth should come from tonal layers, borders, spacing, and fixed hierarchy rather than heavy shadows.

Use the neutral app background behind white cards. Use muted surface fills for inputs, chips, and source context blocks. Use thin dividers for lists and bottom navigation. Shadows are reserved for modal sheets and should be subtle enough that the interface still feels flat and native.

Avoid glassmorphism, floating decorative panels, dramatic gradients, and stacked shadows. The UI should look credible as a production mobile app.

## Shapes

The shape language is soft but controlled.

- Use `rounded.md` (8px) for book cards, source context cards, inputs, and primary buttons.
- Use `rounded.sm` (6px) for compact inline controls.
- Use `rounded.full` only for status badges, filter chips, and avatar-like source marks.
- Avoid mixing many corner radii on one screen.

Phone mockups and system sheets may have platform-native rounding, but in-app cards should stay at 8px or less.

## Components

**Buttons:** Primary buttons are teal with white text and should appear once per screen when possible. Secondary buttons use muted surfaces. Destructive actions use error color sparingly and usually as text or a secondary action.

**Inputs:** Text fields use muted surfaces, 48px height, and clear placeholder text. The source URL field should never be visually noisy because most users arrive through sharing, not manual paste.

**Book cards:** A book card must show only a cover placeholder, title, author when available, and a short synopsis. If cover art is not available or rights are unclear, use a typographic book placeholder rather than a fake cover. The fact that the book appears under Books mentioned is enough confirmation; do not add a Saved badge.

**Book expansion:** Keep book information inline on the Reel detail page in v1. A book card may expand in place for a longer synopsis, but tapping a book should not navigate to a separate book detail page until richer metadata, notes, links, or cross-Reel history exist.

**Book actions:** Users should not edit or remove individual books from a Reel in v1. Books are presented as what was mentioned in the source Reel. Future library behavior may add a small plus action to save a book independently, but the first mockup should keep rows read-only.

**Processing quality:** Confidence is not a user-facing UI element. The app may filter unreliable items internally, but visible book cards should not show confidence percentages, meters, model scores, or evidence labels.

**Source context:** Detail screens may show the Reel video or thumbnail, creator, a cleaned source snippet, and Open source action. Do not expose raw evidence JSON, backend stage names, artifact paths, or provider/debug text. Render the source snippet only when `source_context_snippet` exists and has passed cleanup; otherwise omit the snippet area entirely.

**Source snippet quality:** A useful snippet is short, readable, and helps identify the Reel. It should usually be roughly 40-180 characters after cleanup, not mostly hashtags, mentions, links, promo boilerplate, repeated punctuation, raw transcript debris, or duplicate book-title text. The frontend should not run complex caption heuristics; it should render the cleaned nullable field.

**Reel preview:** Use a centered vertical preview frame with a controlled radius, roughly 70-76% of the screen width on standard phones. Avoid true edge-to-edge full-width video on the detail page because it pushes books too far down and makes the app feel like a video player. If playback is not available in v1, use the downloaded thumbnail or a quiet placeholder in the same frame.

**Share handoff:** The post-share destination is the new Reel detail page, not the saved Reel grid. Show the source preview immediately and place the “Finding books…” state where the books list will appear. Use quiet skeleton book rows under the message instead of step labels. Once processing completes, replace that state with Books mentioned. If the app is backgrounded or closed, the saved Reel remains visible in the home grid.

**Processing copy:** Use a single calm label such as “Finding books…” for user-facing processing. Do not show progress percentages or step labels such as Reading caption, Listening, Scanning text, or Saving books in the normal UI.

**Reel tile status:** Prefer quiet icon-only state indicators over text labels on the home grid. Ready should be visually silent. Processing may use a small muted yellow dot or ring. Failed and no-books states should share the same small muted red attention mark on the grid, because the grid only needs to signal that a tile needs attention. Explain the exact state after the user opens the Reel detail. Avoid permanent green checkmarks on every ready tile because they add noise to the collection.

**No-books detail:** If extraction completes but no useful books are found, the detail screen should feel neutral and recoverable. Show the Reel context, a simple message such as “No books found in this Reel,” and actions to Open source or Remove from saved. Do not make this look like a technical failure.

**Failed detail:** If extraction fails, the detail screen should clearly offer Retry. Keep the copy user-facing and avoid exposing the backend reason unless it gives the user a useful next action.

**Detail actions:** Open source should be easy to find on detail screens. Delete or Remove from saved can be available for the saved Reel but should not dominate. Do not expose book edit/remove actions in v1.

**Reel removal:** Users may remove an entire saved Reel from the Reel detail page in v1, but it must live in a top-right overflow menu rather than as a primary button. The same menu can include Open source. Confirm destructive removal in a bottom sheet.

**Navigation:** Prefer no bottom tab bar in v1. Home should show Mentioned as a small brand element in the top nav and Saved Reels as the screen title. Profile/settings should live behind a top-right profile button. Add tabs only later if Saved, Search, Capture, and Profile become real first-class destinations.

**Profile/settings:** Open profile/settings as a bottom sheet, not a full page, in v1. The sheet can show account email, sign out, privacy, delete account, and How sharing works. Keep it lightweight so profile does not feel like a major destination. Promote settings to a full page only if the surface grows.

**Manual paste:** Include manual paste as a secondary capture action for copied links, testing, and share-sheet fallback. Do not place a large URL input on the home screen by default. Prefer a small top-nav plus action or Paste link button that opens a compact sheet.

**Signed-out state:** Include one lightweight signed-out screen in product mockups. Use a concise explanation of the app and two primary auth options: Continue with Apple and Continue with Google. Do not overdesign onboarding in v1; the signed-in saved-Reel flow is the main product.

**Share extension mockup:** Include a generic iOS-style Share to Mentioned sheet in mockups so the handoff is obvious. The source app should be represented generically as a social Reel, not with exact Instagram UI, logos, brand colors, or copied platform chrome.

**Full mockup board:** The first full mockup board should include exactly eight user-facing screens: signed out, generic share sheet, new Reel detail while Finding books, new Reel detail with Books mentioned, Saved Reels home grid, Reel detail no books found, Reel detail failed with Retry, and profile/settings bottom sheet. Avoid backend/admin/debug screens.

**Reel imagery:** Use realistic but generic video stills for saved Reel thumbnails and detail previews. They should feel like social video frames without copying Instagram UI, logos, captions, brand colors, or recognizable creators. Avoid abstract placeholders unless the source media is truly unavailable.

**Book artwork:** Use simple typographic book placeholders in v1 mockups. Do not create fake realistic covers because that implies cover metadata or rights the product may not have. Placeholders may use initials, title fragments, or quiet geometric composition.

**Empty states:** Empty Saved should suggest sharing a Reel to Mentioned. No-books detail should stay neutral and focused on the source Reel. Avoid cute illustrations that compete with the workflow.

## Do's and Don'ts

- Do make the share-to-Mentioned handoff obvious on first use.
- Do open a newly shared Reel directly in its detail screen.
- Do make saved Reels/posts the primary home collection in v1.
- Do use a two-column thumbnail grid for the saved Reel collection.
- Do keep normal Reel tiles to thumbnail plus tiny creator handle only.
- Do show books as the primary content inside each saved Reel detail.
- Do keep book information inline on Reel detail for v1.
- Do use Mentioned as the small nav brand and Saved Reels as the home title.
- Do present profile/settings as a bottom sheet in v1.
- Do include manual paste as a secondary action, not the primary home surface.
- Do keep signed-out onboarding to one lightweight screen.
- Do include a generic Share to Mentioned handoff screen in full mockup sets.
- Do use the agreed eight-screen set for the first full mockup board.
- Do use realistic generic video stills for Reel thumbnails and previews.
- Do use typographic book placeholders in v1 mockups.
- Do tuck Remove from saved into a Reel detail overflow menu.
- Do keep individual book rows read-only in v1.
- Do keep the source Reel and books mentioned visually connected.
- Do use primary teal for the main action only.
- Do use simple, native controls over custom novelty UI.
- Do keep Instagram and other social-source UI generic; avoid exact logos, copied layouts, or brand colors unless assets are explicitly licensed.
- Do preserve a clear path back to the source Reel through Open source.
- Don't create a desktop dashboard, admin table, or analytics interface for the consumer app.
- Don't make the first screen a global book library in v1.
- Don't add a bottom tab bar in v1 just to expose profile/settings.
- Don't show confidence, raw evidence, stage history, artifact metadata, worker attempts, or provider details in normal user-facing UI.
- Don't merge books across different source posts in the UI unless a later canonicalization feature exists.
- Don't use giant hero sections, marketing copy, purple gradients, beige monochrome palettes, decorative blobs, or stock photography.
- Don't invent book covers or exact source thumbnails when real assets are unavailable or rights are unclear.
- Don't use raw artifact paths, provider debug text, or backend stage internals in user-facing screens.
