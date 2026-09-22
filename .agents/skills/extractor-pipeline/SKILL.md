---
name: extractor-pipeline
description: Use when changing or debugging Instagram URL extraction, media download, Gemini/LLM mention extraction, provider fallbacks, artifact output, labeled evaluation, or tests under src/extraction.
---

# Extractor Pipeline

Use this skill for work in `src/extraction/`, worker extraction behavior, saved
artifacts, and extraction tests.

## First Reads

Read only what is relevant:

- Pipeline orchestration: `src/extraction/pipeline.py`
- Provider schemas: `src/extraction/schemas.py`
- URL and download behavior: `src/extraction/url.py`, `src/extraction/download.py`
- LLM/provider clients: `src/extraction/gemini.py`, `src/extraction/google_books.py`
- Worker integration: `src/worker.py`, `src/jobs/queue.py`, `src/jobs/service.py`
- Tests: `tests/extraction/`, worker tests that assert extraction output
- Labeled evals: `evals/README.md`, `evals/reel-labels.json`, `scripts/score_extraction_eval.py`

## Workflow

1. Identify the extraction path involved: URL parsing, media download, provider call,
   fallback behavior, artifact persistence, or mention normalization.
2. Keep external effects isolated. Mock network, provider, OCR, and subprocess behavior
   in tests unless the user explicitly asks for integration or smoke testing.
3. Use `tmp_path` for filesystem tests and avoid writing real outputs outside test temp
   directories.
4. Treat `data/artifacts/` as generated runtime output. Do not stage it.
5. Preserve configured-provider and fallback behavior. For provider integrations, cover
   both paths in tests.
6. When output or artifact structure changes, update and run the visual manifest flow
   only when saved artifacts are available.

## Validation

Prefer targeted checks first:

```bash
python -m pytest tests/extraction
```

For broader worker impact:

```bash
python -m pytest tests
```

When extraction prompts, schemas, or models change:

```bash
python scripts/score_extraction_eval.py --results outputs/<run>/result.json
```

## Common Risks

- Real network/provider calls in unit tests
- Hardcoded local paths or committing generated artifacts
- Losing fallback behavior when adding a configured provider
- Silent failure that marks jobs done with partial or empty evidence
- Subprocess inputs that are not treated as untrusted
