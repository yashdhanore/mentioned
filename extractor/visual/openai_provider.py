from __future__ import annotations

import base64
from io import BytesIO
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps
from openai import OpenAI

from app.config import Settings
from extractor.visual.models import (
    OpenAIVisualResponse,
    SCHEMA_VERSION,
    VisualImage,
    VisualReconstruction,
)


VISUAL_RECONSTRUCTION_INSTRUCTIONS = """You extract readable text from Instagram frames and post images.
Only use text visible in the provided images, supplied OCR text, and supplied caption context.
Preserve meaningful line breaks and visible title/author relationships.
Return empty strings and arrays when text is not readable.
Do not use web lookup or external knowledge to fill missing titles or authors.
Ignore UI chrome, barcode fragments, prices, publisher blurbs, repeated partial words, and background noise unless it is the main subject.
Candidate mentions are extraction evidence, not canonical recommendations.
When a title or author is inferred from partial cover evidence, mark evidence_basis as partial_cover_inference and cite source IDs."""


def _mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"
    return "image/png"


def _resized_image_bytes(path: Path, max_long_edge: int) -> tuple[bytes, str]:
    with Image.open(path) as opened_image:
        image = ImageOps.exif_transpose(opened_image)
        if max_long_edge > 0 and max(image.size) > max_long_edge:
            resized = image.copy()
            resized.thumbnail((max_long_edge, max_long_edge), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            resized.save(buffer, format="PNG")
            return buffer.getvalue(), "image/png"
    return path.read_bytes(), _mime_type(path)


def _image_data_url(path: Path, max_long_edge: int) -> str:
    content, mime_type = _resized_image_bytes(path, max_long_edge)
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _response_to_dict(response: Any) -> dict[str, Any]:
    if hasattr(response, "model_dump"):
        return response.model_dump(mode="json")
    if hasattr(response, "model_dump_json"):
        return json.loads(response.model_dump_json())
    if isinstance(response, dict):
        return response
    raise TypeError("OpenAI response object cannot be serialized")


def _extract_output_text(response: Any, raw_response: dict[str, Any]) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    parts: list[str] = []
    for output in raw_response.get("output", []):
        if not isinstance(output, dict):
            continue
        for content in output.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") == "refusal":
                refusal = content.get("refusal") or "The model refused the request."
                raise ValueError(f"OpenAI visual extraction refused: {refusal}")
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    if not parts:
        raise ValueError("OpenAI response did not include output text")
    return "\n".join(parts)


def _schema_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "name": "visual_reconstruction",
        "strict": True,
        "schema": VisualReconstruction.model_json_schema(),
    }


def run_openai_visual_reconstruction(
    *,
    llm_input_manifest: dict[str, Any],
    llm_images: list[VisualImage],
    settings: Settings,
) -> OpenAIVisualResponse:
    if settings.openai_api_key is None:
        raise ValueError("OPENAI_API_KEY is required when MULTIMODAL_LLM_PROVIDER=openai")
    if settings.max_llm_calls_per_job < 1:
        raise ValueError("MAX_LLM_CALLS_PER_JOB must be at least 1 for OpenAI extraction")

    client_kwargs: dict[str, Any] = {
        "api_key": settings.openai_api_key,
        "timeout": settings.llm_timeout_seconds,
    }
    if settings.openai_base_url is not None:
        client_kwargs["base_url"] = settings.openai_base_url
    client = OpenAI(**client_kwargs)

    context = {
        "schema_version": SCHEMA_VERSION,
        "job": {
            "job_id": llm_input_manifest.get("job_id"),
            "source_url": llm_input_manifest.get("source_url"),
            "source_kind": llm_input_manifest.get("source_kind"),
        },
        "caption_text": llm_input_manifest.get("caption_text"),
        "ocr_text": llm_input_manifest.get("ocr_text"),
        "images": [entry.manifest_record() for entry in llm_images],
    }
    content: list[dict[str, Any]] = [
        {
            "type": "input_text",
            "text": "Job context JSON:\n" + json.dumps(context, ensure_ascii=True),
        }
    ]
    for image in llm_images:
        content.append(
            {
                "type": "input_image",
                "image_url": _image_data_url(image.path, settings.max_image_long_edge_px),
                "detail": "high",
            }
        )

    response = client.responses.create(
        model=settings.openai_multimodal_model,
        instructions=VISUAL_RECONSTRUCTION_INSTRUCTIONS,
        input=[{"role": "user", "content": content}],
        reasoning={"effort": settings.openai_reasoning_effort},
        text={
            "format": _schema_format(),
            "verbosity": settings.openai_text_verbosity,
        },
        store=settings.openai_store_responses,
    )
    raw_response = _response_to_dict(response)
    output_text = _extract_output_text(response, raw_response)
    parsed = json.loads(output_text)
    reconstruction = VisualReconstruction.model_validate(parsed)
    return OpenAIVisualResponse(
        reconstruction=reconstruction,
        raw_response=raw_response,
        usage=raw_response.get("usage"),
    )
