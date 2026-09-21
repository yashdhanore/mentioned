# Mentioned Agent Guide

Mentioned is a FastAPI, Supabase, Expo, and Astro product for extracting books, products, and places from shared social content.

## Working Model

- Keep this root guide small; put scoped instructions in the nearest nested `AGENTS.md`.
- Before changing a scoped area, read its local guide: [src](src/AGENTS.md), [src/extraction](src/extraction/AGENTS.md), [mobile](mobile/AGENTS.md), [web](web/AGENTS.md), [tests](tests/AGENTS.md), [supabase](supabase/AGENTS.md), or [.agents](.agents/AGENTS.md).
- For product, design, positioning, growth, prioritization, or product-decision work, read [CONTEXT.md](CONTEXT.md), [DESIGN.md](DESIGN.md), [docs/strategy/product.md](docs/strategy/product.md), and [docs/strategy/technical.md](docs/strategy/technical.md) first.
- Do not commit secrets, `.env` files, local databases, generated artifacts, build outputs, or dependency folders.

## Strategy Memory

- When the user discusses product ideas, technical approaches, architecture options, "how should we do this" questions, tradeoffs, or research findings, search [docs/strategy/product.md](docs/strategy/product.md) and [docs/strategy/technical.md](docs/strategy/technical.md) before treating the idea as new.
- If the idea was discussed before, mention the prior note or decision and explain how the current suggestion fits, differs, or conflicts.
- After meaningful product or technical ideation, research, or approach selection, update the appropriate strategy file in the same change with a dated note, decision, rejection, or supersession. Keep product/customer/positioning notes in `product.md`; keep architecture, implementation, cost, privacy, operational, and rejected technical approaches in `technical.md`.
- Technical strategy notes must reference the product constraint they serve, such as the save -> extract -> revisit loop, the book-first wedge, v1 contract safety, cost control, privacy, or future generic saved items.
- Do not add every small implementation detail to the strategy docs; capture durable context that will help future agents recognize repeated ideas, avoid rejected paths, or mature the product and architecture over time.

## Guide Maintenance

- When a change affects commands, setup, directory ownership, dependencies, generated outputs, deployment workflow, Supabase workflow, test strategy, or coding conventions, update this file or the nearest nested `AGENTS.md` in the same change.
- If code, config, and `AGENTS.md` disagree, trust the code/config, fix the guide, and mention the guide update in the closeout.
- Keep new guidance short and scoped; prefer nested `AGENTS.md` files over expanding this root guide.

## Core Commands

- Run the full stack locally (Postgres, API, worker, web, mobile) in one command: `make dev` (see [README](README.md#local-development-full-stack)); stop with `make dev-down`.
- Install backend dev dependencies: `python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- Run the API: `fastapi dev`
- Run the worker: `mentioned-worker` or `python -m src.worker`
- Run backend tests: `pytest`
- Lint/format the backend: `ruff check .` and `ruff format --check .`
- Run mobile checks from `mobile/`: `npm test` (focused scripts plus `lint` and `typecheck`); lint alone with `npm run lint`, format check with `npm run format:check`.
- Run web checks from `web/`: `npm test` (typecheck, build, and Playwright e2e)
- CI runs the backend, mobile, and web checks on every pull request and push to `main`; see `.github/workflows/ci.yml`.

## Shipping Expectations

- Match the existing style and boundaries in the files you touch.
- Add or update focused tests when behavior changes.
- Use Alembic for schema changes in `public`: tables, columns, grants, and row-level security policies all go in a new revision under `migrations/versions/`; prod applies it via `alembic upgrade head` in the worker pre-deploy step. The Supabase CLI owns only storage buckets, auth, and local stack config, nothing in `public`; see [supabase/AGENTS.md](supabase/AGENTS.md).
- For hosted backend failures, inspect Render evidence before guessing from local code.
