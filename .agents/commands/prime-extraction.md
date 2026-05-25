# Prime Extraction

Load focused context for extraction pipeline work.

## Input

Use the user's message after invoking this command as the extraction task, bug,
provider issue, or evaluation question. If blank, build general extraction context.

## Process

1. Read `AGENTS.md`, `README.md`, and `DESIGN.md` if relevant.
2. Inspect extraction code:
   - `src/extraction/pipeline.py`
   - `src/extraction/schemas.py`
   - `src/extraction/download.py`
   - `src/extraction/gemini.py`
   - `src/extraction/google_books.py`
   - `src/extraction/url.py`
3. Inspect storage/artifact behavior when relevant:
   - `src/storage/`
   - `data/artifacts/` structure, without committing generated outputs
   - `evals/visual_regression_manifest.json`
   - `scripts/evaluate_visual_manifest.py`
4. Inspect tests:
   - `tests/extraction/`
   - worker tests that exercise extraction output
5. Identify provider behavior:
   - configured provider path
   - fallback path
   - Gemini/OpenAI/OCR or external binary assumptions
   - local dependencies such as `yt-dlp`, `ffmpeg`, and `tesseract`
6. Identify deterministic testing patterns with `tmp_path`, `monkeypatch`, and mocked
   network/subprocess/provider calls.

## Output

Summarize:

- Extraction task understanding
- Relevant files and data flow
- Existing tests and gaps
- Provider/fallback behavior
- Artifact/eval implications
- Validation commands to use next

Prefer this validation when extraction outputs or artifact structure change:

```bash
python -m pytest tests/extraction
python scripts/evaluate_visual_manifest.py --artifacts-dir data/artifacts
```
