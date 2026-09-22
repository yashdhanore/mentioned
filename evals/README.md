# Extraction Evals

Labeled Reels let us measure extraction quality as precision, recall, and hallucinations instead of mention counts.

## Files

- `reel-labels.json` holds the ground truth for every Reel in `reel-lists/`.
- `reel-lists/*.txt` are the URL lists fed to `scripts/compare_gemini_video_models.py`.
- `reel-lists/gemini-video-model-comparison.md` has the run commands.

## How to label a Reel

Open the Reel, watch it with sound, and read the caption.
Then edit its entry in `reel-labels.json`:

```json
{
  "source_url": "https://www.instagram.com/reel/DVqsAbKjOcX/",
  "list": "smoke-4",
  "status": "labeled",
  "expected_mentions": [
    {"category": "book", "title": "Nineteen Eighty-Four", "author": "George Orwell", "aliases": ["1984"]},
    {"category": "book", "title": "Dune", "author": "Frank Herbert", "optional": true}
  ],
  "notes": "Last book only appears in the background at 0:41."
}
```

- `status`: `todo` until you finish the Reel, then `labeled`.
Use `excluded` for Reels that are deleted, private, or unusable, and say why in `notes`.
- `expected_mentions`: every book, place, or product the creator intentionally features, recommends, or reviews.
This matches the bar in `EXTRACTION_PROMPT` in `src/extraction/gemini.py`.
- A `labeled` Reel with an empty `expected_mentions` list is valid and useful: any prediction on it is a hallucination.
- `category`: `book`, `place`, or `product`.
- `title`: the canonical title; subtitles and a leading "The", "A", or "An" are ignored when matching.
- `author`: optional, for books; only the last name has to match.
- `aliases`: optional alternative titles the model may reasonably output, such as translated titles or `1984`.
- `optional: true`: for borderline items, such as a book visible but never discussed.
Predicting it is not a false positive, and missing it is not a false negative.
- `notes`: free text for anything a future labeler should know.

Label the whole Reel before marking it `labeled`; a half-labeled Reel turns correct predictions into false positives.

Check your edits at any time:

```bash
python scripts/score_extraction_eval.py
```

It validates the file and prints labeling coverage.

## Scoring a model run

```bash
python scripts/compare_gemini_video_models.py \
  --source-file evals/reel-lists/gemini-video-comparison-20.txt \
  --output outputs/gemini-compare-20/result.json
python scripts/score_extraction_eval.py \
  --results outputs/gemini-compare-20/result.json \
  --output outputs/gemini-compare-20/score.json
```

The scorer only counts `labeled` Reels and lists the rest as skipped.
It reports, per model: precision and recall with 95% Wilson intervals, F1, author accuracy, false positives on Reels with nothing to find, mean confidence of correct versus wrong mentions, failed extractions, cost, and cost per correct mention.
`score.json` has the per-Reel true positives, false positives, and misses for error analysis.
