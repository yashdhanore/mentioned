# Mentioned Backend

Validation scaffold for a backend that turns public Instagram Reel and post URLs into readable
text extracted from captions, media metadata, frames, and post images.

## Run the API

```bash
fastapi dev
```

## Run the worker

```bash
python -m worker.run
```

## API

- `POST /v1/jobs/` queues an extraction job for a URL.
- `GET /v1/jobs/{job_id}` returns job status.
- `GET /v1/jobs/{job_id}/result` returns the text-first result:
`caption_text`, `spoken_text`, `visual_text`, `image_text`, `merged_text`, and `warnings`.
- `POST /v1/jobs/{job_id}/rerun` clears prior debug rows and requeues the job.

ASR and multimodal LLM providers are scaffolded as swappable stages. With the default local config,
audio transcription is skipped and visual reconstruction uses OCR output only.

## Optional OpenAI visual extraction

```bash
export OPENAI_API_KEY=...
export MULTIMODAL_LLM_PROVIDER=openai
export OPENAI_MULTIMODAL_MODEL=gpt-5.4-nano
export ASR_PROVIDER=openai
export OPENAI_ASR_MODEL=gpt-4o-mini-transcribe
```

The OpenAI path uses one Responses API call per job with selected frames/images, deterministic crops,
OCR text, and caption context. OCR artifacts are still retained and used as fallback.
When ASR is enabled, the extracted `audio.wav` is sent to OpenAI's audio transcriptions endpoint and
stored as a `transcript` artifact.
