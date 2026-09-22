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
uv run python scripts/compare_gemini_video_models.py \
  --source-file evals/reel-lists/gemini-video-comparison-20.txt \
  --model gemini-2.5-flash --model gemini-3.1-flash-lite \
  --media-dir outputs/gemini-compare-20/media \
  --output outputs/gemini-compare-20/result.json
uv run python scripts/score_extraction_eval.py \
  --results outputs/gemini-compare-20/result.json \
  --output outputs/gemini-compare-20/score.json
```

`--media-dir` keeps the downloaded media next to a `media-manifest.json` per source.
When iterating on the prompt, add `--reuse-media` to rerun the models on that media instead of downloading from Instagram again; a folder is only reused for the exact source URL its manifest names.

The scorer only counts `labeled` Reels and lists the rest as skipped.
It reports, per model: precision and recall with 95% Wilson intervals, F1, author accuracy, false positives on Reels with nothing to find, mean confidence of correct versus wrong mentions, failed extractions, cost, and cost per correct mention.
`score.json` has the per-Reel true positives, false positives, and misses for error analysis.

## Results

Run on 2026-09-22 over the 22 labeled Reels (131 expected books; 2 Reels excluded), one run per configuration.

### Model comparison, current prompt

| Model | Precision [95% CI] | Recall [95% CI] | F1 | FP | Cost per 1,000 correct mentions | Mean seconds |
| --- | --- | --- | --- | --- | --- | --- |
| `gemini-2.5-flash` (previous production default) | 0.963 [0.92, 0.98] | 0.992 [0.96, 1.00] | 0.977 | 5 | $1.26 | 15.2 |
| `gemini-3.1-flash-lite` (production since 2026-09-22) | 0.992 [0.96, 1.00] | 0.992 [0.96, 1.00] | 0.992 | 1 | $0.27 | 11.0 |
| `gemini-3.5-flash-lite` | 0.985 [0.95, 1.00] | 0.992 [0.96, 1.00] | 0.988 | 2 | $0.36 | 10.3 |
| `gemini-3.8-flash` | 1.000 [0.97, 1.00] | 0.992 [0.96, 1.00] | 0.996 | 0 | $1.03 (launch pricing) | 14.2 |

Every model misses the same one book, "Marigold Mind Laundry".
The confidence intervals overlap, so this set shows `gemini-3.1-flash-lite` is no worse than the previous default at about a fifth of the cost; it does not show it is better.
That, plus the 2.5 family being retired model by model, is why `GEMINI_MODEL` now defaults to it.
`gemini-3.8-flash` scores highest and is the fallback if a later run shows Lite degrading, but its launch pricing doubles on 2027-01-01.

### What error analysis changed

1. **Label fixes.**
The first run scored `gemini-2.5-flash` at 0.776 precision and 0.954 recall.
Reading every false positive and miss showed about half of them (20 of 42) were labeling problems: one Reel labeled with the wrong books (now excluded), books mentioned only in passing that should be `optional`, and title variants such as "Monstress" for "Monstress Stories" that needed `aliases`.
Fixing labels, not the model, moved that run from 0.776 precision and 0.954 recall to 0.884 and 0.992, without touching the model or the prompt.
Deciding what counts as a label rather than an error needs care: on one Reel several books flash past in the first second without being recommended, so they are marked `optional`, but only the titles at least two models found independently.
A title only one model produced stays a false positive, because one of them ("The theory of symbolic transformations") is invented.
2. **Places leaking into book Reels.**
The largest remaining error was places: 12 of `gemini-2.5-flash`'s 21 false positives.
A "books around the world" Reel captions each book with its country, and the model returned "Turkey", "Tehran", and "Japan" as recommended places.
The prompt now defines a place as somewhere the creator recommends going and excludes a place that only describes another item.
On the same media, `gemini-2.5-flash` false positives fell from 17 to 5 (precision 0.884 to 0.963), `gemini-3.8-flash` from 9 to 0, and no model lost recall.
3. **Dropped: a confidence threshold.**
After the label fixes, every remaining wrong book in the first run was at confidence 0.8 or below and every correct one at 0.9 or above, which suggested a free threshold.
The next run returned the same wrong books at 1.0, so self-reported confidence is not stable enough to filter on.

### Limits of this set

- Every labeled Reel recommends books; there are no place or product Reels and no Reels with nothing to find.
The places fix is proven to remove false places, not proven harmless for Reels that really recommend a place.
- One run per configuration; the same model and media vary between runs (for example `gemini-3.5-flash-lite` invented 15 garbled titles on one dense list in one run and none in the next).
- What is left is small enough to read one by one: `gemini-2.5-flash`'s 5 false positives are "Boracay" on a Filipino literature Reel, three books that flash past on `DYERlNXPsAU` and one invented title; `gemini-3.1-flash-lite`'s single error is the same Boracay.
At this size, the next real signal has to come from more Reels, not more tuning.

