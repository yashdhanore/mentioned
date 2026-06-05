# Implementation Report: Signed-Out Orbiting Books Product Preview

**GitHub Issue**: N/A

## Summary

Replaced the signed-out lower preview with a central portrait Reel card and four orbiting book covers. The motion uses React Native `Animated` transform-only loops with reduced-motion detection and cleanup. Added the generated local Reel asset and a source-level regression test for the preview behavior.

## Tasks Completed

| Task | Status | Notes |
|------|--------|-------|
| Add Preview Regression Checks | Complete | Added constants and reduced-motion/native-animation source regression; verified the expected initial failure. |
| Create the Central Reel Asset | Complete | Generated and saved `mobile/assets/auth-orbit-reel-preview.png`; verified PNG dimensions are `941x1672`. |
| Rebuild `SignedOutProductPreview` | Complete | Replaced connector diagram with central Reel, orbit guides, four book covers, native-driver loops, and reduced-motion handling. |
| Replace Auth Preview Styles | Complete | Replaced old connector/book-stack preview styles with orbit scene, Reel, guide, and book cover styles. |
| Visual Polish Pass | Complete | Checked CDP-controlled `393x852` and `320x568` viewports against `http://localhost:8082/`; adjusted compact guides/anchors and wrapper overflow for clean fit. |
| Final Validation | Complete | TypeScript, signed-out regressions, full pytest, asset dimensions, and whitespace checks passed. |

## Validation

| Command | Result |
|---------|--------|
| `pytest tests/test_mobile_signed_out_screen.py::test_signed_out_preview_uses_native_reduced_motion_safe_orbit -q` | Failed as expected before implementation because the new asset did not exist. |
| `file mobile/assets/auth-orbit-reel-preview.png` | Passed; PNG image data. |
| `sips -g pixelWidth -g pixelHeight mobile/assets/auth-orbit-reel-preview.png` | Passed; `941x1672`. |
| `cd mobile && npm run typecheck` | Passed. |
| `pytest tests/test_mobile_signed_out_screen.py -q` | Passed; `6 passed`, one existing warning. |
| `python -m pytest` | Passed; `99 passed`, `4 skipped`, one existing warning. |
| `git diff --check` | Passed. |
| CDP visual smoke, `393x852` | Passed; document width matched viewport, CTA/readable preview fit, no screen-edge clipping. |
| CDP visual smoke, `320x568` and scrolled preview | Passed; document width matched viewport, compact preview remained readable and scrollable vertically. |

## Files Changed

| File | Purpose |
|------|---------|
| `tests/test_mobile_signed_out_screen.py` | Added source regression for reduced-motion-safe native orbit preview and asset presence. |
| `mobile/assets/auth-orbit-reel-preview.png` | Added generated portrait Reel image for the central preview card. |
| `mobile/src/components/signed-out-product-preview.tsx` | Rebuilt signed-out preview as central Reel plus four animated orbiting book covers. |
| `mobile/src/styles.ts` | Added orbit preview styles and compact viewport tuning. |
| `.agents/reports/signed-out-orbiting-books-preview-implementation.md` | This implementation report. |

## Deviations From Plan

- Used headless Chrome via Chrome DevTools Protocol for visual smoke checks because the shared MCP browser profile was locked.
- Added compact-only guide styles and adjusted book anchors/scale after visual validation to avoid 320px edge clipping.
- Added `overflow: hidden` and `width: 100%` to `authPreviewWrap` so decorative preview overflow does not create sideways scroll.
- The worktree already had dirty signed-out screen, app mark, and asset changes before implementation; these were preserved and not reverted.

## Follow-Ups

None.
