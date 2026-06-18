# Mentioned Product Dump

Last updated: 2026-06-14

This is the single, messy place for Mentioned product thinking: product improvements,
marketing ideas, positioning, launch angles, user problems, and future bets. Use it as an
idea bank, not as a committed roadmap.

Agents should read this file when discussing product direction, feature ideas, positioning,
growth, marketing, launch plans, or prioritization. Also read `CONTEXT.md` for current product
language, `DESIGN.md` for visual/product feel, and `specs/product-ideas.md` for more technical
roadmap notes.

## How To Use This File

- Keep raw ideas here before turning them into specs, issues, or implementation plans.
- Prefer adding dated notes instead of deleting ideas. Mark ideas as validated, rejected, shipped,
  or superseded when the direction changes.
- Treat bullets here as prompts for discussion, not decisions.
- When an idea becomes actionable, promote it into `specs/`, a plan, or an issue and leave a link
  back here.
- Keep product and marketing language aligned with the current framing: Mentioned is a way to save
  recommendations and useful things mentioned in social content. Books are the first wedge, not the
  whole product.

## Product Thesis

Mentioned helps people capture useful recommendations from social content before they disappear
into feeds, DMs, screenshots, or memory. The first focused use case is extracting books from
Instagram Reels, but the broader product is a personal recommendation memory layer for books,
places, products, restaurants, recipes, travel ideas, posts, and anything else worth coming back to.

The near-term product should prove a tight native capture loop:

- Save a social source from the share sheet.
- Extract useful mentioned items.
- Let the user inspect, correct, and keep what matters.
- Make saved sources and items easy to find again.

The long-term product should help users recall saved content by meaning, context, and intention,
not by exact title, creator, or platform search terms.

## Idea Intake Template

Use this format when adding new ideas:

```md
### YYYY-MM-DD - Short Idea Name

- Type: Product / UX / Marketing / Growth / Technical-product / Research
- Status: Raw / Exploring / Validated / Rejected / Shipped / Superseded
- Audience:
- Problem:
- Idea:
- Why it might matter:
- Smallest test:
- Notes:
```

## Product Improvement Ideas

### Native Capture And First-Run Experience

- Make the share-sheet capture path feel like the primary product, not a secondary input.
- Design onboarding around one clear behavior: "Share a Reel to Mentioned when it mentions a book."
- Add a first successful save moment that shows the source, extracted books, and a clear next action.
- Consider a sample source for new users who install before they have a real Reel ready.
- Make paste-link capture useful, but visually secondary to native capture.

### Extraction Quality And Recovery

- Show extraction as "useful but imperfect" instead of pretending every result is final.
- Give users lightweight correction controls: remove wrong item, retry source, edit title/author,
  mark extraction as wrong.
- Capture failure reasons in user-friendly buckets: unsupported source, private/unavailable source,
  no books found, extraction failed, provider timeout.
- Preserve evidence snippets where possible so users can understand why a book was detected.
- Add confidence signals internally before exposing any quality label to users.

### Saved Sources

- Treat saved sources as memories: source thumbnail, creator/handle when available, date saved,
  extracted items, and source-opening action.
- Let users search or filter saved sources by creator, platform, extracted item, and rough context.
- Consider source notes so a user can write why they saved something.
- Keep source history even when the user does not add every extracted item to a collection.

### Books And Reading

- Turn extracted books into a useful reading list without making the product feel like only a book
  tracker.
- Support states like "want to read", "reading", "finished", "not interested", or keep this simpler
  with saved/removed only until there is enough demand.
- Add book cover enrichment where available, with typographic fallback spines when cover data is
  missing.
- Explore simple export/share formats: reading list image, plain text list, Apple Notes copy, or
  Goodreads/StoryGraph-friendly export later.

### Collections

- Collections should be user-curated, not automatic buckets that pretend every extracted item is
  already accepted.
- Future collections should support mixed item types: books, places, restaurants, products, recipes,
  and travel ideas in one useful list.
- Explore starter collection types: reading list, trip ideas, restaurants to try, products to compare,
  gift ideas, recipes to cook.
- Let one saved source contribute multiple items to multiple collections.

### Semantic Search And Memory

- Start with source recall: "Which Reel mentioned the book about attention?" or "Where did I see
  that cafe in Lisbon?"
- Expand into item lookup after source recall works well.
- Support vague memory queries across source text, extracted item names, evidence snippets, creators,
  and user notes.
- Avoid launching chat before retrieval quality is high enough to feel trustworthy.

### Beyond Books

- Candidate next categories: places, restaurants, products, recipes, travel destinations, hotels,
  quotes, podcasts, essays, outfit ideas, gift ideas.
- The first non-book category should be chosen based on capture frequency, extraction reliability,
  and how clearly users would revisit the saved item.
- Keep product language flexible: "books mentioned" in v1 surfaces, but "things worth remembering"
  in broader positioning.

### Trust, Privacy, And Control

- Be clear that the app saves what the user shares into it; avoid implying background surveillance
  of social apps.
- Make account deletion and data deletion easy to find.
- Avoid storing full media forever unless there is a concrete user-facing or debugging reason.
- Prefer retaining lightweight artifacts like thumbnails, OCR text, transcripts, and extraction
  evidence when useful.

## Marketing And Positioning Ideas

### Positioning Angles

- "Don't lose the books that were mentioned."
- "A memory layer for recommendations hidden in your feed."
- "Save the useful part of the Reel."
- "Turn social recommendations into lists you can actually use."
- "For the things you meant to come back to."

### Audiences

- Readers who save book recommendation Reels.
- People who screenshot recommendations and never revisit them.
- Travel planners collecting restaurants, hotels, neighborhoods, and activities from social videos.
- Gift planners collecting product mentions.
- Creators or curators who want to turn recommendation content into reusable lists.

### Launch And Growth Ideas

- Start with book-focused messaging because it is concrete and emotionally clear.
- Use before/after demos: messy saved Reel -> clean extracted book list.
- Show real capture flow from Instagram share sheet into Mentioned.
- Create short launch videos around common pain: "I know I saved that Reel somewhere."
- Ask early users what they already save: books, restaurants, products, travel, recipes, or quotes.
- Build a waitlist survey around the next category users want after books.

### Content Ideas

- Weekly "books mentioned this week" demo using public recommendation content where allowed.
- Product-building posts about turning chaotic social saves into structured memory.
- Visual examples of a saved source becoming a useful list.
- Comparison posts: screenshots folder vs saved source history vs searchable item list.
- Behind-the-scenes posts on extraction quality, corrections, and privacy choices.

### Website Ideas

- Keep the landing page focused on the actual capture-to-extraction loop.
- Use the website for the broader vision: semantic search, future categories, collections, and
  waitlist interest.
- Avoid promising unavailable app features inside the app; use website roadmap language instead.
- Include a simple category interest poll for books, places, products, restaurants, recipes, travel,
  and other.

## Prioritization Prompts

When deciding what to build next, ask:

- Does this improve the core save -> extract -> revisit loop?
- Does this help the published app feel trustworthy and understandable?
- Does this preserve the book-first wedge while keeping the generic recommendation-memory vision?
- Can this be tested without changing the frozen v1 contract?
- Is this a user-facing product improvement, infrastructure hardening, or marketing experiment?
- What is the smallest version that teaches us whether the idea matters?

## Raw Notes

Add new notes below this line.

### 2026-06-15 - Viral Product Principles

- Type: Product / Growth / Pricing / Marketing / Landing page
- Status: Raw
- Source: https://x.com/marclou/status/2065385672991752210?s=20
- Audience: Early users, future paid subscribers, launch-page visitors, and the product team.
- Problem: Mentioned can easily become too vague: too many categories, too many features, too many
  CTAs, or an expensive free tier that attracts usage before willingness to pay is clear.
- Idea: Use Marc Lou's viral-product principles as a checklist for the landing page, launch assets,
  pricing, and early product packaging. The useful translation for Mentioned:
  - Avoid an unlimited free plan. Prefer bounded free credits, a small number of sample extractions,
    a short trial, a low-cost starter plan, or standalone free marketing tools that do not create
    unbounded extraction cost.
  - Keep the visual system simple: mostly neutral surfaces, clear text, and one accent color reserved
    for the primary action.
  - Replace vague claims with concrete numbers when true, such as saves processed, minutes saved,
    supported source types, or number of books extracted.
  - End pages and launch posts with something worth sharing, not a generic footer.
  - Treat social preview images as conversion assets; design them to make people click.
  - Give each screen or landing-page section one job.
  - Make the headline plain enough that someone outside tech understands it immediately.
  - Validate payment intent early; do not confuse signups with demand.
  - Write copy from real Mentioned use cases, not generic AI productivity language.
  - Show the product flow before explaining the product: source -> extraction -> saved items.
  - Be known for one core promise first: do not lose the useful things mentioned in social content.
  - Keep pricing simple, ideally three obvious choices if/when multiple plans exist.
  - Ride an existing wave: social saves, creator recommendations, AI extraction, personal memory,
    book discovery, travel planning.
  - Reuse customer language from interviews, support messages, waitlist responses, and app reviews.
  - Let the founder be visible in demos, videos, changelogs, and launch content.
  - Make pricing easy to find once the product asks for payment.
  - Test headlines for memorability, not just cleverness.
  - Prefer emotional outcomes over feature labels: relief, confidence, less forgetting, more follow
    through on things users meant to revisit.
  - Look for one surprising interaction or artifact people have not seen before, such as a Reel
    turning into a clean reading list.
  - Make the hero section self-sufficient: a visitor should understand what Mentioned does without
    scrolling.
  - Show empathy before selling by naming the real behavior: saving posts, screenshots, and Reels
    that vanish into clutter.
  - Use one primary CTA per surface.
  - Keep naming memorable and obvious; avoid clever names that require explanation.
  - Sell human desires, not features: remember more, save time, organize taste, plan better, reduce
    digital clutter.
  - Let people experience the product before buying where costs are controlled, such as a demo,
    sample extraction, or limited trial.
  - Avoid weak wording; make claims specific enough to understand and challenge.
  - Question subscription pricing. Consider whether one-time purchases, packs, credits, or annual
    plans better match extraction costs and consumer willingness to pay.
  - Make CTAs describe the next action, such as "Extract My Reel" or "Save This Book List."
  - Collect proof before sending traffic: testimonials, app screenshots, extracted examples, and
    user quotes.
  - Keep the product description under 10 words where possible.
  - Compare against the real alternatives: Instagram saves, screenshots, Notes, bookmarks, and memory.
  - Do not race to the bottom on price if the product delivers a useful memory layer.
- Why it might matter: Mentioned has real per-use costs from media handling, OCR/transcription,
  LLM calls, enrichment, storage, and support. The product also needs clear, memorable positioning
  because the broader vision can sound abstract unless the first wedge is concrete.
- Smallest test: Audit the landing page and app onboarding against this checklist. Track cost per
  successful save, activation rate, extraction volume per user, retry/support burden, headline
  comprehension, and willingness to pay before committing to a permanent free plan or broad launch.
- Notes: Keep the initial published proof accessible enough for learning and App Store trust, but
  design future monetization with explicit usage ceilings and clear upgrade moments.

### 2026-06-15 - Arc Selection Interaction Inspiration

- Type: UX / Product
- Status: Raw
- Audience: Mobile users curating useful extracted items from saved sources.
- Problem: Moving an extracted item into a collection, reading list, or selected set can feel like a
  generic state change if the UI only toggles a checkbox or updates a list silently.
- Idea: Explore an iOS-style selection mode where users tap Select, choose source tiles or extracted
  items, and see the chosen item travel along a curved arc into a destination such as a collection,
  reading list, sample box, or "kept items" tray. Inspiration: Motion's `arc()` path animation, where
  an item moves from source to destination on a curved trajectory instead of a straight line.
- Why it might matter: The motion makes the product model more legible: a useful thing mentioned in
  a source is being intentionally moved into a place the user controls. It could make curation feel
  tactile and memorable without adding explanation text.
- Smallest test: Prototype this only with sample data or a local-only interaction first. Validate
  whether users understand Select -> item flies into destination -> Delete/Remove clears the selected
  set before wiring it to real collection state.
- Notes: Keep it short, optional, and respectful of reduced-motion settings. Avoid using this for
  destructive deletion; the stronger fit is "add to list", "keep", or "collect" because the motion
  visually reinforces where the item went.
