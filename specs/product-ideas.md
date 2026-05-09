# Mentioned Product Ideas

Last updated: 2026-05-09

This is a living backlog for product, architecture, and learning ideas. It is intentionally not a committed roadmap yet; ideas here should be promoted into specs only after we validate the next smallest step.

## Current Product Direction

Mentioned helps users turn social videos into structured saved recommendations. The first focused wedge is book recommendations from Instagram Reels, with room to expand into other collectible entities later.

## Ideas To Preserve

### Book Catalog And Reading Lists

- Introduce a first-class `Book` domain object instead of treating each extraction result as loose mention text.
- Ask the LLM for structured output that maps cleanly into the book type.
- Enrich candidate books through a Books API so results have normalized title, author, cover, identifiers, and metadata.
- Save extracted books into a user catalog.
- Let users create a personal to-read list from extracted books.

### Job And Worker Architecture

- Revisit the current always-running worker model.
- Explore event-driven processing so extraction work starts when a job/event arrives.
- Learn queues through a practical implementation, possibly RabbitMQ, Redis Queue, Celery, Dramatiq, or a managed cloud queue.
- Decide whether database-backed jobs are enough for the current scale or whether a queue should own job delivery.

### Frontend Refactor And UX

- Break down `mobile/App.tsx` into focused components, screens, hooks, and API/state modules.
- Improve the mobile UI beyond placeholder assets.
- Use downloaded reel thumbnails when available instead of generic placeholders.
- Add UX for a book catalog, reading list, saved sources, and job progress.

### Ingestion And Cost Control

- Reduce dependence on sending every downloaded reel directly to Gemini.
- Add cheaper extraction passes before multimodal LLM calls, such as URL parsing, captions, metadata, OCR, transcripts, and frame sampling.
- Use LLM calls as a fallback or confidence booster rather than the default for every input.
- Track provider cost, latency, and confidence per extraction.

### Media And Artifact Retention

- Decide what to do with downloaded reels after extraction.
- Keep lightweight derived artifacts where useful, such as thumbnails, sampled frames, transcript text, OCR output, and evidence snippets.
- Avoid keeping full videos forever unless there is a clear user-facing or debugging need.

### Platform Expansion

- Add TikTok support.
- Add YouTube Shorts support.
- Design platform handling through source adapters so Instagram, TikTok, and YouTube do not leak platform-specific logic across the whole app.

### Generalized Collections

- Explore expanding beyond books into other saved entities:
  - quotes
  - outfit ideas
  - travel destinations
  - hotels
  - products
  - restaurants
- Consider whether the system should model this as typed collections, a generic `SavedItem`, or both.

### Chat And Semantic Search

- Let users chat with or search across their saved lists.
- Use semantic search so users can find things that Instagram itself cannot easily search.
- Start with retrieval/search over saved structured items before building a full chat experience.

## Open Questions

- Is the first product wedge strictly books, or should the architecture support multiple saved item types from day one?
- What book metadata is mandatory for a good first experience: title, author, cover, description, ISBN, published date, categories?
- Should extracted mentions be considered evidence, while books become normalized saved entities?
- What is the retention policy for original downloaded videos?
- What queue/event system is worth learning without adding production complexity too early?
- Should migrations run automatically as part of deploy, manually before deploy, or through a one-off release command?

## Candidate Next Specs

1. Book domain model and Google Books enrichment.
2. Extraction cost-control strategy.
3. Frontend component split and reading-list UX.
4. Job processing architecture and queue migration RFC.
5. Media artifact retention policy.
6. Multi-platform source adapter design.
7. Semantic search over saved items.
