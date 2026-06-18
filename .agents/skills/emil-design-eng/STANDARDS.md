# Emil Design Engineering Standards

## Motion Decision Framework

Ask these in order:

1. How often will users see this?
2. What job does the motion do?
3. What physical origin should it imply?
4. Can it be interrupted?
5. Will it stay smooth under load?
6. What happens for reduced motion and touch devices?

## Frequency Rules

| Frequency | Decision |
| --- | --- |
| 100+ times/day, keyboard shortcuts, command palettes | No animation. |
| Tens of times/day, list navigation, repeated hover sweeps | Remove or drastically reduce. |
| Occasional, modals, drawers, toasts | Standard fast UI motion. |
| Rare, onboarding, celebrations, special feedback | Delight is allowed if it has restraint. |

Raycast-style frequent commands should feel instant. A rare feedback morph can be memorable. The same animation can be right in one context and wrong in another.

## Easing

Use easing as the main taste lever.

```css
:root {
  --ease-out: cubic-bezier(0.23, 1, 0.32, 1);
  --ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);
  --ease-drawer: cubic-bezier(0.32, 0.72, 0, 1);
}
```

- Entering or exiting UI: `ease-out` or a stronger custom ease-out.
- Movement already on screen: custom `ease-in-out`.
- Hover/color feedback: short default `ease` or tokenized color transition.
- Constant motion: `linear`.
- Avoid built-in CSS easings for important motion; they often feel weak.
- Never use `ease-in` for UI entrances. It delays the moment users are watching.

## Duration

| Element | Duration |
| --- | --- |
| Button press | 100-160ms |
| Tooltip or tiny popover | 125-200ms |
| Dropdown/select | 150-250ms |
| Toast | 200-400ms when spatial continuity matters |
| Modal/drawer | 200-500ms depending on distance and gesture |
| Hold-to-delete deliberate phase | Around 2s linear |
| Hold-to-delete release/cancel | Around 200ms ease-out |

UI motion should usually stay under 300ms. Slower motion must be justified by distance, gesture physics, education, or deliberate confirmation.

## Transform And Origin

- Buttons and pressable controls should usually use `active: scale(0.97)` or a nearby subtle value.
- Never enter from `scale(0)`. Use `scale(0.9-0.97)` plus opacity.
- Popovers, dropdowns, and tooltips scale from the trigger. Use Radix/Base UI transform-origin variables when available.
- Modals are the exception: centered modals can keep center origin.
- Percentages in `translate()` are relative to the element itself. Prefer `translateY(100%)` over hard-coded heights for drawers and toasts.
- `scale()` scales children too. Use that for press feedback when icons/text should compress as a unit.
- `rotateX()`, `rotateY()`, `transform-style: preserve-3d`, and `translateZ()` are valid for demonstrative or decorative depth, not routine app chrome.

## Transitions, Keyframes, Springs, And WAAPI

- Prefer CSS transitions for dynamic UI because they retarget smoothly when state changes mid-flight.
- Avoid keyframes for toasts, toggles, menus, or anything users can trigger rapidly; keyframes restart instead of retargeting.
- Use `@starting-style` for modern entry animations when browser support is acceptable.
- Use WAAPI for programmatic animations that should retain compositor performance.
- Use springs for gestures, drag, momentum, and decorative motion that should feel alive.
- Keep spring bounce subtle, usually `0.1-0.3`, and avoid bounce in serious product UI.

## Clip Path

Use `clip-path` as a high-performance reveal primitive.

```css
.reveal {
  clip-path: inset(0 100% 0 0);
  transition: clip-path 200ms var(--ease-out);
}

.reveal[data-open='true'] {
  clip-path: inset(0 0 0 0);
}
```

Good uses:

- Before/after comparison sliders by clipping the top image.
- Scroll image reveals from bottom to top.
- Tab color transitions by duplicating the tab list and clipping the active layer.
- Hold-to-delete overlays with slow linear fill and fast release.
- Text or SVG reveals where width/height animation would cause layout work.

## Gesture Details

- Dismiss on distance or velocity. A quick flick should be enough.
- Apply damping when users drag past a natural boundary.
- Capture the pointer once dragging starts.
- Ignore secondary touches after the first drag begins.
- Prefer friction over hard stops.
- Test drawer and swipe interactions on a real touch device when possible.

## Performance

- Animate `transform`, `opacity`, and carefully chosen `clip-path` first.
- Avoid animating `width`, `height`, `margin`, `padding`, `top`, or `left` for routine motion.
- Avoid updating inheritable CSS variables on a parent every frame; it can recalculate styles for all children.
- Framer Motion shorthand props like `x`, `y`, and `scale` can run on the main thread. Use full `transform` strings for motion that must stay smooth under load.
- CSS animations often hold up better than JavaScript animation during page load.
- Keep blur small. `filter: blur(2px)` can rescue crossfades; heavy blur is expensive, especially in Safari.

## Accessibility

Reduced motion means gentler motion, not necessarily zero visual feedback.

```css
@media (prefers-reduced-motion: reduce) {
  .panel {
    transform: none;
    transition: opacity 160ms ease;
  }
}

@media (hover: hover) and (pointer: fine) {
  .card:hover {
    transform: translateY(-2px);
  }
}
```

- Remove or reduce movement under `prefers-reduced-motion`.
- Keep opacity/color changes when they help comprehension.
- Gate hover motion behind fine-pointer hover media queries.

## Component Craft

### Sonner Principles

- Developer experience matters: render `<Toaster />` once, call `toast()` anywhere.
- Good defaults beat many options.
- Naming creates identity; memorable can beat descriptive.
- Handle invisible edge cases: hidden tabs, stacked hover gaps, pointer capture, rapid additions, swipe direction by position.
- Documentation is part of the component. Let users try the product and copy working code.

### Vaul Principles

- Drawer motion is gesture-first. It needs touch physics, damping, velocity dismissal, and interruptibility.
- `translateY(100%)` hides unknown-height drawers cleanly.
- Use an iOS-like drawer curve when the interaction should feel native.

## Testing Motion

- Slow the animation to 2-5x and inspect the frame-by-frame path.
- Test rapid open/close or rapid add/remove to verify interruptibility.
- Check composited properties in DevTools.
- Review the next day. Taste catches problems after the novelty wears off.
