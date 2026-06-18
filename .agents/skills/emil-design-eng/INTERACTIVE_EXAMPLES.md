# Interactive Examples And Media Review

Use this reference when building article-style demos, reviewing images/videos/animations, or converting visual taste into examples.

## Emil-Style Example Anatomy

A strong interactive example contains:

1. A tiny prompt that tells the user what to compare.
2. Two or more variants that differ by one important property.
3. A direct control: button, slider, dropdown, drag handle, replay button, or hover group.
4. Immediate feedback with no setup.
5. A short explanation after the user can feel the difference.
6. Inspectable implementation details where useful.

Examples from the site:

- Two dropdowns with identical duration but different easing.
- Two popovers where one scales from center and one from the trigger.
- Two buttons where one uses `scale(0)` and one starts around `0.93`.
- Tooltip groups where the first hover delays but subsequent hovers open instantly.
- A blur/no-blur crossfade with a scrubber to inspect frames.
- Comparison sliders and scroll reveals built with `clip-path`.

## Building Demos

Prefer real UI controls over passive videos when practical.

- Use `button` elements for replay and state changes.
- Use sliders for frame or progress scrubbing.
- Use paired examples for judgment training.
- Keep demos narrow; one lesson per island.
- Put the demo in an airy layout so the motion is easy to perceive.
- Let users replay; do not make them refresh the page.
- Add keyboard support unless the demo is specifically about pointer/touch behavior.

## Video And Image Use

Videos should teach motion that cannot be understood from a static screenshot.

- Autoplaying videos should be muted, looping, and `playsinline`.
- Use `preload="metadata"` unless the first frame is essential above the fold.
- Prefer short loops that isolate one behavior.
- Pair video with prose that names exactly what to notice.
- Use images for artifacts, screenshots, tweets, DMs, logos, and before/after visual anchors.
- Keep image corners and framing consistent with the surrounding UI.

## Browser Review Checklist

When reviewing motion in a browser:

- Capture a snapshot to list controls and interactive regions.
- Inspect computed `transition`, `animation`, `transform`, `filter`, `clip-path`, and `transform-origin`.
- Trigger the animation repeatedly and rapidly.
- Test hover chains for tooltip delay behavior.
- Toggle reduced motion if possible.
- Slow the animation or scrub the timeline when judging subtle differences.
- Look for values hidden in utility classes, such as `active:scale-[0.97]` or `transition-[background-color,transform]`.

## Common Demo Fixes

| Problem | Fix |
| --- | --- |
| Passive explanation only | Add a control that lets the user feel the difference. |
| Two variants differ in many ways | Isolate one variable: easing, origin, duration, blur, or scale. |
| Animation plays once | Add replay/reset. |
| Motion is too subtle to evaluate | Add a slow-motion toggle or scrubber. |
| Hover demo fails on touch | Gate hover with media queries and provide tap fallback if needed. |
| Video explains UI that could be live | Build the live interaction unless implementation cost is disproportionate. |

## Taste Notes For Agents

- Great examples do not lecture first. They invite perception first, then explain.
- The reader should leave with language: "wrong origin", "weak easing", "not interruptible", "seen too often", "layout animation", "needs blur".
- A demo that feels good but cannot be explained is not finished. Explain the rule it demonstrates.
