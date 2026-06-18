# Site Research: emilkowal.ski

Research basis: homepage, all linked `/ui/...` writing pages, and project pages linked from the homepage: [animations.dev](https://animations.dev/), [Sonner](https://sonner.emilkowal.ski/), [Vaul](https://vaul.emilkowal.ski/), and [index.how](http://index.how/).

## Homepage

The homepage is intentionally sparse: text-first, neutral, generous whitespace, low ornamentation, and a narrow reading column. It uses hierarchy through weight, spacing, and gray contrast rather than decoration.

Notable observations:

- No inline images or videos on the homepage.
- Navigation is a curated list of projects and writing, not a visual grid.
- Motion is nearly invisible: a hidden promo bar transform and restrained input color transitions.
- The page proves that taste does not require constant visual noise.

## Article Map

- `Agents with Taste`: package judgment into skill files; name why something feels better so agents can follow it.
- `Train Your Judgement`: compare alternatives, pick the better one, then articulate why; judgment improves through explicit contrast.
- `Building an animation course`: packaging matters; logos, hero interactions, physical goods, and platform quality shape perceived value.
- `Building a Toast Component`: Sonner succeeded through name, animation, interruptibility, stacking, swiping, docs, and hidden edge cases.
- `You Don't Need Animations`: animation must have purpose and frequency awareness; delight decays into annoyance when repeated often.
- `Developing Taste`: taste is trained instinct; surround yourself with great work, analyze why it works, and practice.
- `7 Practical Animation Tips`: button scale, avoid `scale(0)`, skip subsequent tooltip delay, choose easing, origin-aware popovers, speed, and blur.
- `Animating in Public`: sharing polished motion work creates opportunity and sharpens craft.
- `The Magic of Clip Path`: `clip-path` powers comparison sliders, image reveals, scroll progress, tab transitions, and hold interactions.
- `Good vs Great Animations`: origin, easing, custom curves, spring-based interactions, and tool knowledge separate good from great.
- `Great Animations`: great motion is natural, fast, purposeful, performant, interruptible, accessible, and hard.
- `CSS Transforms`: transforms are the foundation: translate percentages, scale children, rotate/3D, transform origin, and toast/drawer mechanics.
- `Building a Drawer Component`: drawer quality comes from gestures, velocity, damping, scroll interaction, mobile behavior, and edge cases.
- `Building a Hold to Delete Component`: `clip-path` supports deliberate destructive confirmation with asymmetric timing.

## Media And Visual Patterns

The writing pages often use autoplaying, muted, looping videos to demonstrate motion. Many videos are interactive examples rather than decorative media. The crawler found videos on `Agents with Taste`, `Building an animation course`, `Building a Toast Component`, `You Don't Need Animations`, `7 Practical Animation Tips`, `Animating in Public`, `The Magic of Clip Path`, `Good vs Great Animations`, `Great Animations`, and `CSS Transforms`.

Image-heavy pages:

- `Building an animation course`: many avatars, course/platform screenshots, brand assets, stickers, and marketing visuals.
- `Animating in Public`: screenshots, DMs, and before/after light/dark visual artifacts.
- `The Magic of Clip Path`: before/after Raycast-like images, Figma stroke screenshot, and scroll-reveal imagery.
- `Great Animations` and `CSS Transforms`: small game/app images used as concrete visual anchors.

Visual language:

- Neutral grays and black/white surfaces.
- Rounded cards and screenshots when media appears.
- Tight components inside very airy article layouts.
- Interactive islands embedded in prose.
- Demonstrations that let the reader feel the difference, then read the explanation.

## Project Pages

### animations.dev

A course/marketing page built around interactive learning. It foregrounds the problem: code alone is not enough; bad easing or duration can ruin an animation. It uses many images, logos, reviews, and interactive demos like toasts, drawers, paste buttons, and exercises.

Agent lesson: when teaching craft, create comparisons and exercises. Do not only list rules.

### Sonner

A focused docs/demo page for an opinionated toast component. It exposes installation, usage, toast types, positions, expand behavior, rich colors, close button, headless mode, GitHub, and docs.

Agent lesson: great components need great defaults, low-friction API, visible demos, and copyable usage.

### Vaul

A minimal drawer component page with one primary demo: open the drawer. The restraint matches the component's purpose.

Agent lesson: a demo page can be tiny if the component interaction carries the value.

### index.how

A sparse design education teaser with minimal content and imagery.

Agent lesson: under-explaining can be a deliberate brand choice when intrigue is the point.

## Taste Transfer Pattern

When creating a skill from visual taste:

1. Inspect live pages, not only text extracts.
2. Record examples where two variants differ.
3. Convert the preference into a rule with a reason.
4. Add concrete values where possible.
5. Include verification steps so agents can check the work visually.
6. Keep the skill concise and move deep reference material into one-level files.
