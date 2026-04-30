# Mentioned Text Extraction Backend Specification

Status: Draft v3 (backend-only, Instagram-first, text-first, multimodal extraction planned)

Last updated: 2026-04-29

Purpose: Define a backend service that turns public Instagram Reel and Instagram post URLs into
readable text content extracted from captions, audio, video frames, and post images. This version
updates the original v2 spec with the backend that now exists in this repository and the next
multimodal extraction design.

## Source Basis

This spec is based on:

- The prior `spec.md` v2 text-first extraction contract.
- The implemented FastAPI, SQLModel, worker, artifact, and pipeline code in this repository.
- Manual review of job `71c452b8-801a-461a-a9e0-9f8da4ce586b`.
- OpenAI developer documentation consulted on 2026-04-29:
  - `https://developers.openai.com/api/docs/models/gpt-5.4-nano`
  - `https://developers.openai.com/api/docs/guides/latest-model#using-reasoning-models`
  - `https://developers.openai.com/api/docs/guides/migrate-to-responses#responses-benefits`
  - `https://developers.openai.com/api/docs/guides/structured-outputs`
  - `https://developers.openai.com/api/docs/guides/function-calling#strict-mode`

Relevant OpenAI doc guidance used here:

- `gpt-5.4-nano` is described as the cheapest GPT-5.4-class model for simple high-volume tasks,
  including data extraction.
- The latest-model guidance recommends the Responses API for reasoning models, explicit reasoning
  controls, verbosity controls, prompt caching, and Structured Outputs instead of prompt-only schema
  instructions.
- The Responses API supports flexible multimodal inputs, vision, and Structured Outputs.
- Structured Outputs should be preferred when the application needs strict JSON matching a schema.
- Strict schemas require `additionalProperties: false` for objects and required properties; optional
  fields should be represented with nullable types.

## Normative Language

The key words `MUST`, `MUST NOT`, `REQUIRED`, `SHOULD`, `SHOULD NOT`, `RECOMMENDED`, `MAY`, and
`OPTIONAL` in this document are to be interpreted as described in RFC 2119.

`Implementation-defined` means the behavior is part of the implementation contract, but this
specification does not prescribe one universal policy. Implementations MUST document the selected
behavior.

## 1. Product Boundary

Mentioned v1 is a backend extraction service.

The primary product contract remains:

```text
Instagram Reel/Post URL -> readable text content from the post
```

The API result is text-first, but the visual extraction layer SHOULD also identify visible
candidate mentions such as title/author pairs when they can be read directly from frames or post
images. These candidates are extraction evidence, not canonical recommendations.

The output SHOULD include text from:

- Instagram caption/description where available.
- Spoken audio transcript for Reels, once ASR is configured.
- Visible on-screen text in video frames.
- Visible text in static or carousel post images.
- Multimodal LLM reconstruction of hard-to-read visual text.

Important v1 boundaries:

- Mentioned v1 is Instagram-first.
- Mentioned v1 outputs text, not final recommendation entities.
- Mentioned v1 does not output recommendation rankings or external-record matches as the primary
  API contract.
- Mentioned v1 does not add items to Goodreads or any other destination.
- Mentioned v1 does not include frontend, mobile UI, auth, or user libraries.

The pipeline SHOULD produce candidate mentions, titles, authors, or structured visual items as
debug/evaluation evidence when the source image supports them. Those internal structures MUST NOT
claim canonical identity, rankings, or save destinations until a later product decision changes the
contract.

## 2. Current Implementation Baseline

The repository currently implements the first backend milestone.

Implemented API endpoints:

- `GET /healthz`
- `POST /v1/jobs/`
- `GET /v1/jobs/{job_id}`
- `GET /v1/jobs/{job_id}/result`
- `POST /v1/jobs/{job_id}/rerun`

Implemented storage:

- SQLite via SQLModel for local development.
- Local filesystem artifact storage under `data/artifacts/{job_id}`.
- Job rows with status, current stage, progress, and error fields.
- Stage run rows with duration, payload, and error text.
- Artifact rows with kind, path, metadata, and timestamp.
- Text result rows using the `TextResult` table.

Implemented result contract:

```json
{
  "job_id": "...",
  "source_url": "...",
  "source_kind": "instagram_reel",
  "status": "succeeded",
  "current_stage": "completed",
  "progress": 1.0,
  "text": {
    "caption_text": "...",
    "spoken_text": null,
    "visual_text": "...",
    "image_text": null,
    "merged_text": "...",
    "warnings": [],
    "debug": {}
  },
  "stage_runs": [],
  "artifacts": []
}
```

Implemented extraction stages:

1. `normalize_url`
2. `fetch_html`
3. `parse_page`
4. `probe_source_media_or_images`
5. `download_media_or_images`
6. `extract_audio`
7. `transcribe_audio`
8. `sample_frames`
9. `select_images`
10. `ocr_layout`
11. `multimodal_llm_extract`
12. `assemble_text_result`

Current provider behavior:

- `yt-dlp` probes and downloads public Instagram media where available.
- `ffmpeg` extracts audio and samples frames.
- Tesseract is used as a baseline OCR path through `analyze_frames`.
- ASR is not configured; `spoken_text` is currently skipped with a warning.
- Multimodal LLM extraction is not configured; visual reconstruction currently falls back to OCR
  only and emits a warning.

Planned MVP behavior when OpenAI is configured:

- OCR SHOULD still run on selected frames and crops.
- One OpenAI `gpt-5.4-nano` call SHOULD also run using the selected images, crops, OCR text, and
  caption context.
- The OpenAI visual extraction call SHOULD NOT transcribe or infer spoken audio.
- The result SHOULD keep both OCR artifacts and LLM artifacts so extraction quality can be compared
  job by job.

Current artifact kinds include:

- `source_html`
- `page_meta`
- `probe`
- `media`
- `audio`
- `frames`
- `selected_frames`
- `post_images`
- `ocr`
- `text_result`

## 3. Lessons From Job 71c452b8-801a-461a-a9e0-9f8da4ce586b

The example job succeeded end-to-end, but its visual text quality exposed the next important
problem.

Observed source:

- Instagram Reel: `https://www.instagram.com/reel/DVqsAbKjOcX/`
- Source kind: `instagram_reel`
- Job status: `succeeded`
- Selected frame count: 8
- OCR visual text length: 2110
- ASR provider: none
- Multimodal LLM provider: none

Observed quality:

- The selected frames were useful and visually represented the reel well.
- Full-frame OCR was noisy because it read book covers, barcodes, prices, partial words,
  background texture, and repeated near-duplicate frames as one large text stream.
- The most important user-facing text was visible in the selected frames:
  - The intro concept: five classics that changed the way the creator thinks.
  - Reasons such as "It reminded me of the brutal consequences of being vain and morally corrupt."
  - Book cover/title/author evidence for Dorian Gray, Song of Solomon, Letters from a Stoic,
    The Idiot, and Nineteen Eighty-Four.
- The current final `visual_text` did not preserve that content cleanly.

Conclusion:

Frame selection is good enough for the next milestone. The weak link is the extraction and assembly
strategy after frame selection.

Required change:

The pipeline SHOULD add deterministic visual crops and a multimodal LLM reconstruction step. The
LLM should receive selected frames, crops, OCR text, caption context, and a strict JSON schema. The
result should replace noisy full-frame OCR as the preferred `visual_text` when confidence and
schema validation pass.

## 4. Goals and Non-Goals

### 4.1 Goals

- Preserve the existing text-first API.
- Improve visible text quality for Reels and posts with hard-to-read visual text.
- Add a provider interface for multimodal extraction.
- Use OpenAI Responses API as the first multimodal LLM provider.
- Default to `gpt-5.4-nano` for cheap high-volume extraction.
- Make exactly one `gpt-5.4-nano` multimodal call per job in the MVP, with no fallback model and
  no retry call.
- Use Structured Outputs for model results.
- Implement only `none` and `openai` multimodal provider modes in the MVP.
- Keep OCR as a local baseline and as context for the LLM.
- Generate deterministic crops before OCR/LLM extraction.
- Extract visible title/author-style candidate mentions when they can be read from frames or post
  images.
- Keep candidate mention schema generic across books, products, newsletters, people, and unknown
  categories, while optimizing the first prompts and eval set around book reels.
- Preserve artifacts needed for evaluation and debugging.
- Add an evaluation loop that measures quality, latency, and cost per job.

### 4.2 Non-Goals

- Public API changes that expose canonical recommendation entities as the primary result.
- Book lookup, canonicalization, ranking, or Goodreads integration.
- Web search to infer unseen titles or authors. The model MAY use visual recognition of partial
  covers when the image evidence is strong, but those outputs MUST be marked as inferred.
- Downloading private Instagram content.
- Sending Instagram credentials through the extraction pipeline.
- A frontend review UI.
- General TikTok or YouTube Shorts support in the next milestone.

## 5. System Architecture

The backend SHOULD stay separated into these layers:

1. Transport Layer
   - FastAPI routes and request/response schemas.
   - Performs request validation only.
   - MUST NOT run heavy extraction inside HTTP handlers.

2. Job Layer
   - Job creation, claim, rerun, status transitions, result assembly.
   - Owns durable job state.

3. Source Layer
   - Instagram URL normalization, source kind detection, HTML fetch, public metadata parsing,
     probe/download behavior.

4. Media Layer
   - `yt-dlp`, `ffmpeg`, audio extraction, frame sampling, image selection.

5. Visual Signal Layer
   - Frame selection, crop generation, OCR/layout extraction, image manifests.

6. Model Layer
   - Multimodal LLM calls over selected images/crops with strict schemas.
   - Provider-specific code MUST be isolated.

7. Assembly Layer
   - Caption, transcript, OCR, and LLM visual reconstruction cleanup.
   - Dedupe and final text section assembly.

8. Evaluation Layer
   - Dataset replay, expected output comparison, quality metrics, cost/latency reporting.

9. Observability Layer
   - Stage runs, artifacts, logs, timings, provider errors, token/image usage.

## 6. Domain Model

### 6.1 Existing Models

`Job`

- `id`
- `source_url`
- `source_kind`
- `status`
- `current_stage`
- `progress`
- `error_code`
- `error_message`
- `created_at`
- `updated_at`

`StageRun`

- `job_id`
- `stage`
- `success`
- `duration_ms`
- `payload_json`
- `error_text`
- `created_at`

`Artifact`

- `job_id`
- `kind`
- `path`
- `metadata_json`
- `created_at`

`TextResult`

- `job_id`
- `caption_text`
- `spoken_text`
- `visual_text`
- `image_text`
- `merged_text`
- `warnings_json`
- `debug_json`
- `created_at`
- `updated_at`

`BookCandidate`

- Exists in the model layer from earlier work.
- MUST remain out of the primary v1 API response unless a later spec changes that decision.
- MAY be repurposed or superseded by a more general `CandidateMention` model in a later milestone.

### 6.2 Planned Internal Models

`ImageSelection`

- Logical record for selected frames and selected post images.
- SHOULD store source path, role, frame timestamp if available, dimensions, and hash.

`VisualCrop`

- Represents deterministic crops derived from selected images.
- Fields:
  - `id`
  - `job_id`
  - `source_image_id`
  - `crop_role`
  - `path`
  - `bbox_normalized`
  - `width`
  - `height`
  - `metadata_json`

Crop roles SHOULD include:

- `full_frame_context`
- `overlay_text_region`
- `book_or_object_region`
- `post_image_context`
- `ocr_text_dense_region`

`LLMExtraction`

- Represents one provider call.
- Fields:
  - `id`
  - `job_id`
  - `provider`
  - `model`
  - `request_manifest_path`
  - `response_path`
  - `schema_version`
  - `success`
  - `duration_ms`
  - `input_image_count`
  - `input_token_count`
  - `output_token_count`
  - `estimated_cost_usd`
  - `error_text`
  - `created_at`

This can start as artifacts and debug JSON before becoming a first-class SQL table.

`CandidateMention`

- Internal structure for visible title/author-style extraction evidence in the next milestone.
- SHOULD be generic, not book-only.
- SHOULD support books, products, newsletters, people, and unknown categories.
- The MVP prompt examples and evaluation set SHOULD focus on book reels first.
- SHOULD capture visible labels, optional author/creator text, source image/crop IDs, and confidence.
- MUST be treated as extraction evidence, not canonical entity identity, ranking, or save target.

## 7. API Contract

The public result contract remains text-first.

`GET /v1/jobs/{job_id}/result` MUST return:

- Job metadata.
- Text result.
- Stage runs.
- Artifacts.

The `text` object MUST keep these fields:

- `caption_text`
- `spoken_text`
- `visual_text`
- `image_text`
- `merged_text`
- `warnings`
- `debug`

`visual_text` and `image_text` SHOULD prefer the best cleaned visual reconstruction for their
respective source types:

1. Validated multimodal LLM `cleaned_frame_text` for `visual_text` and
   `cleaned_post_image_text` for `image_text`, when available and not rejected by quality gates.
2. OCR text after cleanup, only when no valid LLM output is available.
3. `null`, when no useful visual text is available.

When OCR and OpenAI both succeed, `visual_text` or `image_text` SHOULD contain only the cleaned
OpenAI reconstruction for that source type. OCR output SHOULD remain in the `ocr` artifact and MAY
be summarized in `debug` for comparison, but it SHOULD NOT be concatenated into public text fields.

Partial-cover inferred candidates MUST NOT be inserted into `visual_text` or `image_text` unless
the title/author text is also directly readable or reconstructed from visible media text.
Normalized inferred titles/authors SHOULD live under `text.debug.candidate_mentions` with
`evidence_basis = "partial_cover_inference"`.

`debug` MAY include internal LLM metadata and crop metadata, but MUST NOT expose secrets or
sensitive provider request headers.

When validated candidate mentions are available, `/result` SHOULD include a lightweight copy under
`text.debug.candidate_mentions` for manual verification. The complete validated structured output
SHOULD be stored as an artifact rather than expanded into the primary response.

For the local MVP, valid candidate mentions SHOULD NOT be hidden from `text.debug` by a confidence
threshold. Each candidate should expose its confidence and evidence basis so weak inferences can be
reviewed. Later hosted or product-facing surfaces MAY add filtering.

`debug` SHOULD include a small OCR/OpenAI comparison summary when both OCR and OpenAI run:

```json
{
  "ocr_openai_comparison": {
    "frame_text_source": "openai|ocr|none",
    "post_image_text_source": "openai|ocr|none",
    "ocr_visual_text_length": 2110,
    "ocr_image_text_length": 0,
    "openai_frame_text_length": 420,
    "openai_post_image_text_length": 0,
    "candidate_mentions_count": 5,
    "partial_cover_inference_count": 1,
    "ocr_artifact_path": "data/artifacts/{job_id}/ocr.json",
    "llm_output_artifact_path": "data/artifacts/{job_id}/llm_output.json"
  }
}
```

Example future result shape:

```json
{
  "text": {
    "caption_text": "What are some books that completely changed the way you see the world?",
    "spoken_text": null,
    "visual_text": "Five classics that changed the way I think\nThe Picture of Dorian Gray - Oscar Wilde\nIt reminded me of the brutal consequences of being vain and morally corrupt\nSong of Solomon - Toni Morrison\nIt showed me the importance of understanding one's own origins\nLetters from a Stoic - Seneca\nIt taught me important lessons about managing emotions and setbacks\nThe Idiot - Fyodor Dostoevsky\nIt warned me of what naive goodness looks like in the real world\nNineteen Eighty-Four - George Orwell\nIt reminded me that 2+2=4, no matter what",
    "image_text": null,
    "merged_text": "Caption:\n...\n\nVisible text:\n...",
    "warnings": [
      "ASR provider is not configured; spoken_text was not extracted."
    ],
    "debug": {
      "visual_reconstruction_provider": "openai",
      "visual_reconstruction_model": "gpt-5.4-nano",
      "visual_reconstruction_confidence": 0.86,
      "candidate_mentions": [
        {
          "label": "The Picture of Dorian Gray",
          "author": "Oscar Wilde",
          "category": "book",
          "visible_evidence": "The Picture of Dorian Gray - Oscar Wilde",
          "confidence": 0.91
        }
      ]
    }
  }
}
```

## 8. Pipeline Stages

The next milestone SHOULD use this stage order:

1. `normalize_url`
   - Normalize and validate the URL.
   - Detect source kind and platform ID.

2. `fetch_html`
   - Fetch public HTML when possible.
   - Store `source_html`.

3. `parse_page`
   - Extract title, caption, description, and available metadata.
   - Store `page_meta`.

4. `probe_source_media_or_images`
   - Use `yt-dlp` or adapter-specific tools to inspect public media.
   - Store `probe`.

5. `download_media_or_images`
   - Download video or images.
   - Store `media` or `post_images`.

6. `extract_audio`
   - Extract audio from Reels.
   - Store `audio`.

7. `transcribe_audio`
   - Current default: skipped with provider `none`.
   - Future providers MAY include OpenAI speech-to-text, local Whisper, or another ASR provider.
   - ASR MUST remain separate from visual OpenAI extraction.

8. `sample_frames`
   - Sample frames from video media.
   - Store `frames`.

9. `select_images`
   - Select a small representative set of frames/post images.
   - Current default for frames: up to 8.
   - Store `selected_frames`.

10. `generate_crops`
    - New stage.
    - Generate deterministic crops from selected frames and selected post images.
    - MUST run for both Reels and static/carousel posts when selected images are available.
    - Store `crops` and `llm_input_manifest`.

11. `ocr_layout`
    - Run OCR on selected full images and crops.
    - Preserve source IDs and line-level confidence where supported.
    - Store `ocr`.

12. `multimodal_llm_extract`
    - Call the configured provider when enabled.
    - Use selected images, crops, OCR text, caption context, and strict schema.
    - MUST NOT be responsible for audio transcription.
    - Store `llm_output` and usage metadata.

13. `assemble_text_result`
    - Choose the best visual text source.
    - Dedupe, section, and write the final `TextResult`.
    - Store `text_result`.

## 9. Crop Strategy

The crop strategy is a complement to the multimodal LLM, not a replacement for it.

Why crops are needed:

- Full-frame OCR reads too much background noise.
- The LLM benefits from being shown the relevant region and the whole frame context.
- Crops reduce input size and cost.
- Crops make evaluation easier because evidence is localized.
- Static and carousel post images can have the same tiny text, cover, and product-card issues as
  Reels, so crop generation SHOULD support both.

Required crop types:

1. Full-frame context image
   - A manifest entry pointing at the selected frame or post image.
   - Used so the model understands the scene and relationship between text and object.
   - SHOULD keep the source file in `selected_frames` or the selected post-image path rather than
     duplicating it into `crops`.

2. Overlay text crop
   - A broad upper or central region where creator-added text usually appears.
   - For vertical Reels, initial heuristic SHOULD include the upper 65% of the frame.

3. Book/object region crop
   - A lower or central region where books, products, or cards are usually displayed.
   - For vertical Reels, initial heuristic SHOULD include the lower 50% of the frame.

Deferred crop types:

1. Text-dense OCR crop
   - Future optimization based on OCR boxes or image processing.
   - Useful when text is not in the default overlay region.
   - SHOULD NOT be required for the MVP.

Crop implementation requirements:

- Use predictable crop IDs:
  - `frame_003_full`
  - `frame_003_overlay`
  - `frame_003_object`
  - `post_002_full`
  - `post_002_overlay`
  - `post_002_object`
- Derived crop filenames SHOULD match crop IDs, such as `frame_003_overlay.png` and
  `post_002_object.png`.
- Full-frame context entries SHOULD have role `full` in the manifest but SHOULD NOT be copied into
  the `crops` directory.
- Store crop coordinates as normalized bounding boxes.
- Store crop dimensions and source image references.
- Deduplicate near-identical images/crops using perceptual hashing or a simpler initial hash.
- Limit the number of LLM input images to keep costs predictable.
- Keep full-frame context available, but prefer cropped regions for OCR.
- Keep the MVP deterministic and simple: full-frame context, overlay crop, and book/object crop.

Initial limits:

- `max_selected_frames`: 8
- `max_selected_post_images`: 10
- `max_llm_images`: 20
- `max_llm_crops`: 12
- `max_llm_calls_per_job`: 1
- `max_image_long_edge_px`: implementation-defined, RECOMMENDED 1280 or lower for cost control.

## 10. Multimodal LLM Strategy

### 10.1 Provider Choice

The first provider SHOULD be OpenAI via the Responses API.

Default model:

- `gpt-5.4-nano`

Rationale:

- OpenAI docs describe it as the cheapest GPT-5.4-class model.
- The task is primarily image-grounded data extraction and cleanup, not deep reasoning.
- The output is constrained by a schema, which reduces the need for a larger model.

Call policy:

- The MVP MUST make at most one multimodal LLM call per job.
- The call MUST use `gpt-5.4-nano`.
- The single call SHOULD include the selected frames, selected post images, generated crops, OCR
  text, and caption context together.
- Full selected images SHOULD provide scene context, while crops SHOULD focus the model on readable
  overlay text and object/book-cover evidence.
- Every image and crop sent to the model MUST have a stable ID and role so the model can cite
  evidence in `visible_text_blocks` and `candidate_mentions`.
- The MVP MUST NOT call a fallback model.
- The MVP MUST NOT retry failed schema validation with a second model call.
- If the single model call fails or returns invalid output, the pipeline SHOULD fall back to OCR
  visual text and emit a warning.

Recommended Responses settings:

- `reasoning.effort`: `low`
- `text.verbosity`: `low`
- `store`: `false` by default, unless product policy changes.
- `text.format`: Structured Outputs JSON schema.
- `text.format.type`: `json_schema`.
- `text.format.strict`: `true`.

The provider interface SHOULD be clean enough to allow other providers later, but the MVP MUST only
support `none` and `openai`.

### 10.2 Prompt Policy

The model MUST be instructed to:

- Extract only text visible in the provided images or present in supplied OCR/caption context.
- Preserve meaningful line breaks and title/author relationships when visible.
- Produce normalized title/author candidate mentions from partial covers when visual evidence is
  strong enough, even if every character is not fully readable.
- Mark whether each candidate mention was directly read from visible text or inferred from visual
  cover evidence.
- Ignore UI chrome, barcode fragments, prices, publisher blurbs, repeated partial words, and
  unreadable background noise unless they are the main subject.
- Return uncertainty when text is not readable.
- Return empty arrays or empty strings instead of guessing.
- Not use web lookup to fill missing titles/authors.

Stable instructions and the JSON schema SHOULD be placed before dynamic job context to benefit from
prompt caching.

### 10.3 Input Manifest

The LLM input manifest SHOULD include:

- `job_id`
- `source_url`
- `source_kind`
- `caption_text`
- `ocr_text`
- `selected_images`
- `crops`
- `expected_output_schema_version`
- `provider`
- `model`

Each image/crop entry SHOULD include:

- `id`
- `role`
- `path`
- `source_image_id`
- `frame_index`
- `timestamp_seconds`
- `bbox_normalized`
- `width`
- `height`

The manifest MUST include both selected full-frame/post-image context entries and generated crop
entries when both are available.

Image and crop IDs SHOULD be stable and human-readable. Frame-derived IDs SHOULD use
`frame_{index}_{role}` and post-image-derived IDs SHOULD use `post_{index}_{role}`, with
zero-padded indexes such as `frame_003_overlay` and `post_002_object`.

Artifact filenames SHOULD match the image/crop ID plus extension, so the model citation ID,
manifest ID, artifact filename, and debug output all refer to the same item.

Full-frame manifest entries SHOULD use role `full` and point to files in `selected_frames` or the
selected post-image path. Only derived overlay/object crops SHOULD be written into the `crops`
directory.

## 11. Structured Output Schema

The multimodal LLM output MUST use OpenAI Structured Outputs with `strict: true` and MUST be
validated against a versioned JSON schema.

Initial schema version: `visual_reconstruction.v1`

Schema requirements:

- Every object in the schema MUST set `additionalProperties: false`.
- All fields MUST be listed in `required`.
- Optional fields MUST be represented as nullable types, such as `["string", "null"]`.
- The schema SHOULD be stable across jobs so provider-side schema processing/caching can work
  predictably.

Conceptual shape:

```json
{
  "schema_version": "visual_reconstruction.v1",
  "cleaned_frame_text": "string",
  "cleaned_post_image_text": "string",
  "confidence": 0.0,
  "visible_text_blocks": [
    {
      "text": "string",
      "kind": "overlay|title|author|subtitle|object_text|ui|background|unknown",
      "source_surface": "frame|post_image",
      "source_image_ids": ["string"],
      "source_crop_ids": ["string"],
      "confidence": 0.0,
      "include_in_merged_text": true,
      "ignored_reason": "string|null"
    }
  ],
  "candidate_mentions": [
    {
      "label": "string",
      "author_or_creator": "string|null",
      "category": "book|product|newsletter|person|unknown",
      "evidence_basis": "direct_visible_text|partial_cover_inference|caption_context|mixed",
      "creator_supplied_context": "string|null",
      "visible_evidence": "string",
      "normalization_notes": "string|null",
      "source_image_ids": ["string"],
      "source_crop_ids": ["string"],
      "confidence": 0.0
    }
  ],
  "ignored_text_summary": "string|null",
  "uncertainty_notes": ["string"]
}
```

Validation rules:

- `cleaned_frame_text` MUST be a string. It MAY be empty.
- `cleaned_post_image_text` MUST be a string. It MAY be empty.
- `confidence` MUST be between 0 and 1.
- The OpenAI response MUST parse through the strict Structured Outputs schema before being used.
- `visible_text_blocks` MUST cite at least one source image or crop when non-empty.
- `visible_text_blocks.source_surface` MUST be `frame` or `post_image`.
- `candidate_mentions` are visible extraction evidence. They MAY be exposed in `text.debug` or
  artifacts for verification, but MUST NOT be treated as canonical entities.
- `candidate_mentions.evidence_basis` MUST distinguish directly read text from partial-cover
  visual inference.
- Partial-cover inferred candidates SHOULD require high confidence and supporting source image/crop
  IDs.
- Partial-cover inferred candidates SHOULD appear in `text.debug.candidate_mentions` and the full
  structured artifact, not in `cleaned_frame_text` or `cleaned_post_image_text`, unless the
  normalized title/author text is also readable from the media.
- The local MVP SHOULD expose all valid candidate mentions in `text.debug.candidate_mentions`
  regardless of confidence. Confidence is shown for review rather than used for hiding.
- Partial-cover inference MUST NOT use web lookup during the job.
- If strict structured parsing fails, the pipeline MUST reject the LLM result.
- The MVP MUST NOT issue a repair or fallback model call after strict parsing failure.
- If strict parsing fails, the pipeline SHOULD fall back to OCR visual text and emit a warning.
- After strict parsing succeeds, the application SHOULD still run app-level checks for source image
  IDs, source crop IDs, confidence ranges, and text grounding rules.

## 12. Text Assembly Rules

The assembler SHOULD use this precedence:

1. Caption text from page metadata and probe description.
2. Spoken text from ASR, when configured.
3. `cleaned_frame_text` from validated LLM output for `visual_text`.
4. `cleaned_post_image_text` from validated LLM output for `image_text`.
5. Cleaned OCR text when LLM output is unavailable or rejected.

Section assembly:

- `caption_text` contains Instagram caption/description only.
- `spoken_text` contains transcript text only.
- `visual_text` contains video-frame visual text only.
- `visual_text` MUST stay grounded to directly readable or reconstructed media text.
- `visual_text` MUST NOT include normalized partial-cover inferred candidates unless that text is
  also readable in the media.
- `image_text` contains static/carousel image text only.
- `image_text` SHOULD follow the same OpenAI-over-OCR reconstruction policy as `visual_text`.
- `image_text` MUST NOT include normalized partial-cover inferred candidates unless that text is
  also readable in the media.
- `merged_text` combines sections with labels.

Deduplication:

- Exact duplicate lines SHOULD be removed.
- Generic source labels such as `Instagram`, `Instagram Reel`, or `Instagram photo` SHOULD be
  removed.
- Near-duplicate repeated frames SHOULD not create repeated text.
- The assembler SHOULD prefer higher confidence LLM text over noisy OCR when both are available.
- The assembler SHOULD NOT concatenate OCR output with valid OpenAI reconstruction in `visual_text`
  or `image_text`.

Warnings:

- Missing ASR provider SHOULD emit a warning when audio exists.
- Missing multimodal LLM provider SHOULD emit a warning when selected images exist.
- Rejected LLM output SHOULD emit a warning with a non-secret error summary.
- No useful extracted text MUST produce a failed result with `error_code = "no_text"`.

## 13. Configuration

Current settings:

- `DATABASE_URL`
- `DATA_DIR`
- `WORKER_POLL_INTERVAL_SECONDS`

Planned settings:

- `ASR_PROVIDER`
- `OCR_PROVIDER`
- `MULTIMODAL_LLM_PROVIDER`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MULTIMODAL_MODEL`
- `OPENAI_REASONING_EFFORT`
- `OPENAI_TEXT_VERBOSITY`
- `OPENAI_STORE_RESPONSES`
- `MAX_SELECTED_FRAMES`
- `MAX_SELECTED_POST_IMAGES`
- `MAX_LLM_IMAGES`
- `MAX_LLM_CROPS`
- `MAX_LLM_CALLS_PER_JOB`
- `MAX_IMAGE_LONG_EDGE_PX`
- `LLM_TIMEOUT_SECONDS`
- `ARTIFACT_RETENTION_DAYS` before hosted production

Recommended defaults:

```text
ASR_PROVIDER=none
OCR_PROVIDER=tesseract
MULTIMODAL_LLM_PROVIDER=none
OPENAI_MULTIMODAL_MODEL=gpt-5.4-nano
OPENAI_REASONING_EFFORT=low
OPENAI_TEXT_VERBOSITY=low
OPENAI_STORE_RESPONSES=false
MAX_SELECTED_FRAMES=8
MAX_SELECTED_POST_IMAGES=10
MAX_LLM_IMAGES=20
MAX_LLM_CROPS=12
MAX_LLM_CALLS_PER_JOB=1
MAX_IMAGE_LONG_EDGE_PX=1280
LLM_TIMEOUT_SECONDS=60
```

The default provider remains `none` so local development can run without paid API credentials.

Local artifact retention:

- Local artifacts SHOULD be retained until explicit deletion or job rerun.
- The MVP SHOULD NOT automatically delete local artifacts, because selected frames, crops, OCR, and
  LLM outputs are needed for verification.
- Rerun SHOULD reuse the same job artifact directory and overwrite deterministic files rather than
  creating a new job artifact directory.
- Rerun manifests and database artifact rows SHOULD represent the latest run. Stale files that are
  not referenced by the latest manifest or artifact rows SHOULD be ignored.
- Hosted production SHOULD add `ARTIFACT_RETENTION_DAYS` or an equivalent retention policy before
  storing user jobs long term.

## 14. Artifacts

Existing artifact kinds MUST continue to work.

New artifact kinds:

- `crops`
- `image_selection_manifest`
- `llm_input_manifest`
- `llm_output`
- `llm_usage`
- `visual_reconstruction`

Artifact requirements:

- Paths MUST be local filesystem paths in local development.
- Metadata MUST be JSON-serializable.
- Provider responses MAY be stored for debugging, but secrets MUST NOT be stored.
- Image manifests SHOULD make it possible to reproduce a provider call from artifacts.
- LLM output artifacts SHOULD include schema version, provider, model, validation status, and usage
  metadata.
- The full validated visual reconstruction output, including all `candidate_mentions`, SHOULD be
  stored as an `llm_output` or `visual_reconstruction` artifact.

## 15. Status and Error Semantics

Job statuses:

- `queued`
- `running`
- `succeeded`
- `partial`
- `failed`

Recommended semantics:

- `succeeded`: all required extraction stages completed and useful text was produced.
- `partial`: useful text was produced but one or more nonfatal stages failed.
- `failed`: no useful text was produced or a fatal setup error occurred.

Stage failures:

- HTML fetch failure SHOULD be nonfatal if media probing/downloading can still proceed.
- Probe/download failure SHOULD be nonfatal if caption text is available.
- OCR failure SHOULD be nonfatal if LLM visual reconstruction succeeds.
- LLM failure SHOULD be nonfatal if OCR visual text or caption text is available.
- OpenAI strict parse failure SHOULD mark the `multimodal_llm_extract` stage failed. If OCR,
  caption, or other text still produces useful output, the job SHOULD finish as `partial`.
- If `MULTIMODAL_LLM_PROVIDER=none`, skipping OpenAI is intentional configuration and SHOULD NOT
  downgrade the job to `partial`. The job MAY still `succeed` with a warning when OCR, caption,
  or other text produces useful output.
- Only configured OpenAI execution failure SHOULD downgrade an otherwise useful job to `partial`.
- ASR absence SHOULD be nonfatal.

## 16. Evaluation

The next milestone SHOULD run OCR and OpenAI side by side when OpenAI is configured. Evaluation
does not need to block local use of the OpenAI path; instead, each job should preserve both OCR
artifacts and LLM artifacts so accuracy can be inspected from `/result` and the artifact directory.

Evaluation dataset:

- A small checked-in or local-only manifest of public URLs and expected text.
- Labeled examples SHOULD be added as real failures and successes are observed.
- At least 10 Instagram Reels are RECOMMENDED before serious prompt/crop tuning.
- The first eval set SHOULD focus on book reels, while keeping labels compatible with the generic
  candidate mention schema.
- Include examples with:
  - overlay text
  - book covers
  - product cards
  - fast cuts
  - static posts
  - noisy backgrounds
  - duplicated frames

Per-job labels SHOULD include:

- Expected `caption_text`, when available.
- Expected key visible lines.
- Expected visible candidate mentions where title/author-style text is readable.
- Expected inferred candidate mentions where partial covers are visually obvious.
- Known irrelevant text that should be ignored.

Metrics:

- Key visible line recall.
- Noise rate in `visual_text`.
- Hallucination rate.
- Structured output parse success.
- Candidate mention precision/recall for internal analysis.
- Direct-read versus partial-cover inference accuracy.
- Total job latency.
- LLM latency.
- Estimated cost per job.
- Single-call failure rate.

Acceptance target for job `71c452b8-801a-461a-a9e0-9f8da4ce586b`:

- `visual_text` SHOULD include the five visible book/reason pairings cleanly.
- `visual_text` SHOULD avoid barcode, price, publisher blurb, OCR fragments, and repeated duplicate
  noise.
- The job SHOULD still succeed when ASR is unavailable.
- The result SHOULD include a warning for missing ASR only, assuming multimodal LLM is configured
  and succeeds.
- Internal candidate mentions SHOULD include the visible book titles and authors when readable from
  the selected frames/crops.

## 17. Security and Privacy

The service MUST:

- Accept only user-submitted public URLs.
- Avoid storing API keys, request headers, cookies, or credentials in artifacts/logs.
- Avoid sending Instagram credentials to source adapters.
- Treat provider responses and artifacts as potentially user-sensitive.
- Default OpenAI response storage to disabled where supported by the API configuration.
- Make vendor/provider behavior explicit in configuration.

The service SHOULD:

- Support artifact retention limits.
- Support deleting job artifacts and rows.
- Redact secrets from exceptions before persisting stage errors.
- Document whether regional processing endpoints are used. OpenAI docs note regional processing
  endpoint pricing behavior for `gpt-5.4-nano`; this is a deployment decision, not a local default.

## 18. Local Development Contract

Local development SHOULD remain possible without paid providers:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
python -m worker.run
```

Basic local API flow:

```bash
curl -s http://127.0.0.1:8000/healthz

curl -s -X POST http://127.0.0.1:8000/v1/jobs/ \
  -H 'Content-Type: application/json' \
  -d '{"source_url":"https://www.instagram.com/reel/DVqsAbKjOcX/"}'

curl -s http://127.0.0.1:8000/v1/jobs/{job_id}

curl -s http://127.0.0.1:8000/v1/jobs/{job_id}/result
```

When `MULTIMODAL_LLM_PROVIDER=none`, the pipeline SHOULD behave as it does today and warn that
visual reconstruction used OCR only.

When `MULTIMODAL_LLM_PROVIDER=openai`, local development requires:

```bash
export OPENAI_API_KEY=...
export MULTIMODAL_LLM_PROVIDER=openai
export OPENAI_MULTIMODAL_MODEL=gpt-5.4-nano
```

## 19. Implementation Plan

### Milestone A: Deterministic Crop Generation

- Add `extractor/stages/generate_crops.py`.
- Generate overlay, object/book, and full-frame context crops.
- Represent full-frame context as manifest entries pointing at `selected_frames`; do not copy full
  frames into the `crops` directory.
- Do not implement OCR-box/text-density crop discovery in the MVP.
- Write crop files under `data/artifacts/{job_id}/crops`.
- Add `crops` and `llm_input_manifest` artifacts.
- Keep behavior deterministic and provider-independent.

### Milestone B: OpenAI Multimodal Provider

- Add an OpenAI client wrapper isolated under `extractor/clients/openai_client.py` or equivalent.
- Use Responses API.
- Send selected images/crops and context.
- Request Structured Outputs with schema `visual_reconstruction.v1`.
- Use exactly one `gpt-5.4-nano` call per job in the MVP.
- Do not implement a fallback model or repair retry in the MVP.
- Extract visible candidate mentions, including title and author when readable.
- Store raw validated output and usage metadata as artifacts.

### Milestone C: Assembly Upgrade

- Make `assemble_text_result` prefer validated LLM `cleaned_frame_text` for `visual_text`.
- Make `assemble_text_result` prefer validated LLM `cleaned_post_image_text` for `image_text`.
- Preserve OCR fallback.
- Add warnings for LLM failures and schema validation failures.
- Include minimal provider/model/confidence metadata in `text.debug`.
- Include lightweight candidate mentions in `text.debug.candidate_mentions` for manual
  verification.
- Include `text.debug.ocr_openai_comparison` with selected text source, text lengths, candidate
  counts, and OCR/LLM artifact paths.
- Store the complete validated structured output as an artifact.

### Milestone D: Evaluation Harness

- Add a small manifest-driven evaluator.
- Measure visual text recall, candidate mention accuracy, noise, hallucination, parse success,
  latency, and estimated cost.
- Include the example job as a regression case.

### Milestone E: ASR Provider

- Add ASR once visual extraction is stable.
- Keep ASR independent from the multimodal work.
- Do not ask the visual OpenAI extraction call to infer spoken audio.

## 20. Open Product and Engineering Decisions

Resolved decision:

1. The next milestone SHOULD read title/author-style candidate mentions when they are visible in
   frames or post images. These candidates are used for verification and evaluation, not canonical
   book lookup.
2. Candidate mentions SHOULD be returned in `text.debug.candidate_mentions` for easy `/result`
   verification, and the complete validated structured output SHOULD be stored as an artifact.
3. The MVP SHOULD make exactly one `gpt-5.4-nano` multimodal call per job. It SHOULD NOT include a
   fallback model or repair retry. If that call fails or validates poorly, the pipeline should use
   OCR fallback and warnings.
4. The MVP SHOULD implement only `none` and `openai` multimodal provider modes. Other providers can
   be added after OpenAI extraction has eval data.
5. Local artifacts SHOULD be retained until explicit deletion or job rerun. A future
   `ARTIFACT_RETENTION_DAYS` setting SHOULD be added before hosted production.
6. When OpenAI is configured, the MVP SHOULD run both OCR and the single OpenAI nano call, preserve
   both outputs, and use that side-by-side result for verification instead of blocking OpenAI use on
   a fixed labeled-example threshold.
7. When OCR and OpenAI both succeed, public `visual_text` and `image_text` SHOULD contain only the
   cleaned OpenAI reconstruction for their source type. OCR SHOULD remain in artifacts and optional
   debug comparison metadata.
8. The OpenAI output SHOULD both read visible text and infer obvious normalized title/author
   candidates from partial covers when visual evidence is strong. Inferred candidates MUST be marked
   with an evidence basis and confidence.
9. Partial-cover inferred candidates SHOULD stay out of public `visual_text` and `image_text` and
   appear only in `text.debug.candidate_mentions` plus the structured artifact, unless the same text
   is readable from the media.
10. The candidate mention schema SHOULD remain generic across content categories, but the MVP prompt
    examples and eval set SHOULD optimize for book reels first.
11. The single OpenAI call SHOULD send both selected full frames/post images and generated crops.
    Every image/crop MUST have a stable ID and role so model evidence can cite the source cleanly.
12. The MVP crop strategy SHOULD stay deterministic and simple: full-frame context, overlay crop,
    and book/object crop. OCR-box or text-density crop discovery can be optimized later.
13. OpenAI extraction MUST use strict Structured Outputs with a versioned JSON schema. If strict
    parsing fails, the LLM result is rejected and the pipeline falls back to OCR without a repair or
    fallback model call.
14. OpenAI stage failure, including strict parse failure, SHOULD make the job `partial` when OCR,
    caption, or other extracted text still provides useful output.
15. `MULTIMODAL_LLM_PROVIDER=none` is intentional configuration and SHOULD NOT downgrade a useful
    OCR/caption result to `partial`; only configured OpenAI execution failure should do that.
16. ASR SHOULD remain separate from image/frame extraction. The OpenAI visual extraction call SHOULD
    NOT transcribe or infer spoken audio.
17. Implementation SHOULD start with deterministic crop generation before OpenAI API wiring, because
    crops are cheap, testable, and improve the later model input.
18. Image and crop IDs SHOULD be predictable and human-readable, using patterns like
    `frame_003_full`, `frame_003_overlay`, `frame_003_object`, `post_002_full`,
    `post_002_overlay`, and `post_002_object`.
19. Crop/image artifact filenames SHOULD match their IDs, such as `frame_003_overlay.png`, so
    citations, manifest entries, artifact paths, and debug output line up.
20. Full-frame context SHOULD stay in `selected_frames` or the selected post-image path and appear
    in the manifest with role `full`; only derived overlay/object crops should be written into
    `crops`.
21. Deterministic crop generation SHOULD run for both Reels and static/carousel Instagram posts
    when selected images are available.
22. For static/carousel posts, `image_text` SHOULD use the same cleaned OpenAI-over-OCR
    reconstruction policy that `visual_text` uses for Reels.
23. The OpenAI structured output SHOULD have separate `cleaned_frame_text` and
    `cleaned_post_image_text` fields so assembly can populate `visual_text` and `image_text`
    without guessing source type.
24. `visible_text_blocks` SHOULD include `source_surface` with `frame` or `post_image` so routing,
    filtering, and debugging do not depend on ID parsing.
25. The local MVP SHOULD expose all valid `candidate_mentions` in `text.debug` regardless of
    confidence; confidence is shown for manual review rather than used to hide weak candidates.
26. Rerun SHOULD reuse the same job artifact directory and overwrite deterministic files. Latest
    manifests and database artifact rows define the current run.
27. `/result` debug SHOULD include `ocr_openai_comparison` with chosen text sources, OCR/OpenAI text
    lengths, candidate counts, and OCR/LLM artifact paths.

These decisions remain open and should be resolved before implementation:

- None.

Current recommendation:

- Keep the public API text-first.
- Extract candidate mentions now, expose the lightweight form through `text.debug`, and keep the
  complete model output in artifacts rather than as canonical top-level entities.
- Implement deterministic crops first.
- Then add OpenAI `gpt-5.4-nano` with Structured Outputs.
- Support only `none` and `openai` provider modes in the MVP.
- Keep the MVP to one nano call per job and use OCR fallback on model failure.
- Run OCR and OpenAI side by side when OpenAI is configured, and build labeled eval data from those
  outputs over time.
