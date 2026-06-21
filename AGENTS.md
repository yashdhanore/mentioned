# Mentioned Agent Guide

Mentioned is a FastAPI, Supabase, Expo, and Astro product for extracting books, products, and places from shared social content.

## Working Model

- Keep this root guide small; put scoped instructions in the nearest nested `AGENTS.md`.
- Before changing a scoped area, read its local guide: [src](src/AGENTS.md), [src/extraction](src/extraction/AGENTS.md), [mobile](mobile/AGENTS.md), [web](web/AGENTS.md), [tests](tests/AGENTS.md), [supabase](supabase/AGENTS.md), or [.agents](.agents/AGENTS.md).
- For product, design, positioning, growth, or prioritization work, read [CONTEXT.md](CONTEXT.md), [DESIGN.md](DESIGN.md), and [PRODUCT.md](PRODUCT.md) first.
- Do not commit secrets, `.env` files, local databases, generated artifacts, build outputs, or dependency folders.

## Core Commands

- Install backend dev dependencies: `python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- Run the API: `fastapi dev`
- Run the worker: `mentioned-worker` or `python -m src.worker`
- Run backend tests: `pytest`
- Run mobile checks from `mobile/`: `npm run typecheck`
- Run web checks from `web/`: `npm test`

## Shipping Expectations

- Match the existing style and boundaries in the files you touch.
- Add or update focused tests when behavior changes.
- Use the Supabase CLI for schema, migration, seed, RLS, or Supabase config changes; see [supabase/AGENTS.md](supabase/AGENTS.md).
- For hosted backend failures, inspect Render evidence before guessing from local code.
