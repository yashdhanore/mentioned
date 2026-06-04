# Mentioned UX/UI Audit

Date: 2026-06-04

## Evidence

- `01-current-signed-out-expo-web.png`: Fresh Expo web capture of the current signed-out screen.
- `02-supplied-three-screen-concept.png`: User-provided three-screen concept/reference showing signed-out, saved Reels, and Reel detail.

Capture limit: the local browser could only reach the signed-out screen because the Expo build read Supabase auth configuration from the environment. I attempted a clean-cache blank-env run, but the app still rendered the auth path. Signed-in, paste, processing, and result states are audited from source code and the supplied concept image, not from live interaction.

## Audited Flow Steps

1. Signed-out entry: healthy foundation, but too static.
2. Shared-while-signed-out: strategically important, currently framed as an auth/error interruption.
3. Home/saved grid: weak saved-list surface; currently reads like storage.
4. Paste sheet: functional utility entry; under-validates and lacks instant positive feedback.
5. Post-submit processing detail: highest-impact activation moment; currently lacks enough confidence and completion feedback.
6. Extracted-books result: clear but plain; it does not yet make the captured list feel reliable and easy to reuse later.
7. No-books/failed states: serviceable recovery copy, but too little reassurance or alternate action.

## Highest-Impact Screen

The highest-impact improvement is the post-submit detail flow: paste/share -> processing -> extracted book names.

Reason: `submitSourceUrl` creates an optimistic capture and immediately opens detail after the user submits a source. That means the detail screen is the first real activation moment, where Mentioned either feels like a trustworthy extraction utility or like a generic background job. Today it shows a large source preview, a quiet processing skeleton, then a plain book list.

The home grid is the second-highest priority. It is the retention/re-entry surface, but it currently says "Saved items" and "Items you have saved", and tiles do not expose enough of the saved book names.

## P0 Findings

1. The first completion moment is underplayed.

Evidence: `mobile/src/features/captures/use-captures.ts` creates and opens a processing capture immediately after job creation. `mobile/src/components/books.tsx` renders "Finding books..." with skeleton rows, then "Books mentioned" with plain rows.

Recommendation: redesign the detail screen around a confidence sequence:
- Immediate "Saved" confirmation.
- Progress steps: "Reading the Reel", "Extracting book names", "Checking book details".
- Completion state: "Book names saved" or "5 book names ready", not "Found 5 books from this Reel".
- A clean extracted list with book covers when available.
- V1 next actions: "Open source", "Copy names", and "Save another Reel". Defer richer reading-list actions to V2.

2. Available book metadata is discarded.

Evidence: API types expose `google_books_url` and `cover_image_url`, but `captureFromJobDetail` maps books to title, author, initials, color, and `synopsis: null`.

Recommendation: carry `cover_image_url` and `google_books_url` into `BookMention`. Use real cover art when available, fall back to generated spines only when missing, and make each row tappable.

3. Share-while-signed-out loses momentum.

Evidence: pending shared sources are preserved, but the signed-out screen still leads with generic auth copy and a warning message.

Recommendation: when launched from a share intent, change the whole signed-out surface to "1 Reel ready to save" and "Continue to find the books". After sign-in, show "Saving your shared Reel..." rather than dropping users into generic app state.

## P1 Findings

4. The home grid is an archive, not a useful saved-list surface.

Evidence: home title is "Saved items"; tile accessibility and visible metadata center on creator/status, not the extracted book names.

Recommendation:
- Rename to "Books from your Reels" or "Saved Reels".
- Show practical counts: "12 book names saved", "3 processing", "1 needs retry".
- Add tile utility: mini book covers, first one or two book names, source label, and clear status labels.
- Make the primary capture action thumb-reachable, not only a small top-right plus.

5. Processing feedback is visually and emotionally thin.

Evidence: processing state is skeleton-only and does not show time expectation, notification reassurance, or milestones.

Recommendation: hide backend internals, but show human progress. After a few seconds, offer "You can leave; we'll notify you." Add a polling fallback while detail is open so users are not dependent on realtime events alone.

6. Push permission likely happens too early.

Evidence: push registration runs as soon as the user is signed in.

Recommendation: ask for notifications inside the first processing flow, after "Saved" is established. Notification copy should be utility based, e.g. "Your book names are ready", not generic "processed" or discovery language like "We found 2 books".

7. Paste link lacks instant validation and confidence feedback.

Evidence: paste submit only checks non-empty before calling the API.

Recommendation: validate Instagram Reel/post URLs client-side, disable "Find books" until valid, add "Paste from clipboard", and show an inline success cue such as "Instagram Reel detected".

## P2 Findings

8. No-books and failed states do not preserve a positive saved-item feeling.

Recommendation: frame both as "Saved anyway". Add "Try another Reel", "Open on Instagram", "Retry", and possibly "Add book manually". For failures, show a plain-language reason when safe.

9. The visual system is coherent but too muted.

Evidence: palette is heavily neutral/green, and current signed-out capture is clean but quiet. The supplied concept is stronger because it uses realistic media, creator handles, view/time metadata, and richer book cards.

Recommendation: keep the calm bookish base, but add more contrast and moments of color through covers, success badges, source metadata, and active saved/ready states.

10. Typography and fonts may not match the intended token system.

Evidence: design tokens mention product font choices, while the React Native theme only defines sizes/weights and no font families.

Recommendation: load and apply the intended fonts, then tune large-title line heights for mobile readability.

## Accessibility And Ergonomics Risks

1. Bottom sheets lack clear modal/focus semantics and explicit close controls.
2. Loading and busy states are mostly visual; shared buttons do not expose busy state.
3. Icon and compact controls are 40px high, below a comfortable 44-48px target.
4. Reel tiles announce only the creator, not status, snippet, or result.
5. Paste input has a visual label but no explicit accessibility label or submit behavior.
6. Decorative preview text may be read as real content by screen readers.
7. Motion does not appear to respect reduced-motion settings.
8. Disabled opacity may reduce contrast too far.

## Recommended Design Direction

Use the supplied three-screen concept as the north star, but sharpen the V1 utility mechanics:

- Signed out: real-looking Reel preview, stronger Google button, and share-intent variant.
- Home: saved Reels grid with extracted book names visible on every tile.
- Detail: source on top, but extracted names visible sooner and more clearly.
- Book cards: real covers, source context, and easy copying/opening.
- Processing: progress milestones, subtle motion, and notification opt-in after save confidence.

V2 note: explicit reading-list/collection mechanics should come later. V1 should focus on extracting the names from a Reel the user already watched, preserving the source, and making the resulting list easy to revisit.

## Suggested Implementation Order

1. Upgrade `BookMention` data and result cards to support cover URLs and external book links.
2. Redesign the detail processing/result section as the extraction completion moment.
3. Add client-side paste validation and clipboard affordance.
4. Improve home grid tile metadata and status labels.
5. Add share-intent-specific signed-out copy and pending-source treatment.
6. Fix shared accessibility primitives: buttons, sheets, headings, tile labels, loading labels.
