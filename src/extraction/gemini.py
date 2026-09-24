from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai.types import GenerateContentConfig, Part

from src.config import get_settings
from src.extraction.download import check_media_size_limits
from src.extraction.gemini_client import get_gemini_client
from src.observability import (
    describe_error,
    gemini_usage,
    langfuse,
    media_placeholder,
    media_view,
    observe_step,
    record_gemini_reply,
    text_part,
    user_message,
)

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
Analyze this Instagram content (video with audio, or images).
Identify all books, products, and places that are explicitly mentioned, shown, or recommended.

Rules:
- Only include items clearly and intentionally featured or recommended
- For books: include author if visible or spoken
- Confidence is between 0.0 and 1.0 and reflects how certain you are (visible cover = high, just mentioned in passing = lower)
- Do NOT include incidental background items, UI elements, or generic references
- A place is a specific location the creator recommends going to, such as a restaurant, shop, hotel, beach, landmark, or a destination pitched as a trip
- Do NOT list a place that only describes another item, such as the country or city a book is set in, where an author is from, or an on-screen label like "Turkey" next to a book
- For places: set location_hint to the city, region, or country the place is in, if the content shows or says it
- For each item you include under the rules above, give evidence of where it is featured: the timestamp (MM:SS) where it is first clearly shown or said, whether that is speech, on_screen_text, or visual (such as a book cover), and a short quote of the words spoken or shown. Evidence does not make an item qualify: a book that only flashes past is still incidental
"""

MENTION_SCHEMA = {
    "type": "object",
    "properties": {
        "mentions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "author": {"type": "string"},
                    "category": {"type": "string", "enum": ["book", "product", "place"]},
                    "confidence": {"type": "number"},
                    "location_hint": {"type": "string"},
                    "evidence": {
                        "type": "object",
                        "properties": {
                            "timestamp": {"type": "string"},
                            "source": {
                                "type": "string",
                                "enum": ["speech", "on_screen_text", "visual"],
                            },
                            "quote": {"type": "string"},
                        },
                        "required": ["source"],
                    },
                },
                "required": ["title", "category", "confidence"],
            },
        }
    },
    "required": ["mentions"],
}

# Traces carry this so quality and cost can be compared across prompt and schema changes.
EXTRACTION_PROMPT_VERSION = hashlib.sha256(
    (EXTRACTION_PROMPT + json.dumps(MENTION_SCHEMA, sort_keys=True)).encode()
).hexdigest()[:12]
EXTRACTION_TEMPERATURE = 0.1

INLINE_SIZE_LIMIT = 20 * 1024 * 1024
VERTEX_INLINE_SIZE_LIMIT = 100 * 1024 * 1024
FILE_POLL_INTERVAL_SECONDS = 2
FILE_POLL_TIMEOUT_SECONDS = 120
RETRY_DELAYS_SECONDS = [2, 5, 10]
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
# The SDK lets httpx timeouts and dropped connections through unwrapped. A slow Gemini
# period shows up as a read timeout, and one of those used to fail the whole save.
RETRYABLE_TRANSPORT_ERRORS = (httpx.TimeoutException, httpx.NetworkError)


def _mime_type_for(path: Path) -> str:
    suffix = path.suffix.lower()
    mime_map = {
        ".3gp": "video/3gpp",
        ".3gpp": "video/3gpp",
        ".avi": "video/avi",
        ".flv": "video/x-flv",
        ".m4v": "video/mp4",
        ".mkv": "video/x-matroska",
        ".mp4": "video/mp4",
        ".mpeg": "video/mpeg",
        ".mpg": "video/mpg",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
        ".wmv": "video/wmv",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    return mime_map.get(suffix, "application/octet-stream")


def upload_to_gemini(client: genai.Client, media_path: Path, *, use_vertexai: bool = False) -> Part:
    file_size = media_path.stat().st_size
    mime_type = _mime_type_for(media_path)
    inline_limit = VERTEX_INLINE_SIZE_LIMIT if use_vertexai else INLINE_SIZE_LIMIT

    if file_size <= inline_limit:
        data = media_path.read_bytes()
        return Part.from_bytes(data=data, mime_type=mime_type)

    if use_vertexai:
        size_mb = file_size / 1024 / 1024
        limit_mb = VERTEX_INLINE_SIZE_LIMIT / 1024 / 1024
        raise RuntimeError(
            f"Vertex AI local media is {size_mb:.1f} MB, above the inline limit of "
            f"{limit_mb:.0f} MB. Upload the media to Google Cloud Storage and pass "
            "a gs:// URI for larger inputs."
        )

    uploaded = client.files.upload(file=media_path, config={"mime_type": mime_type})
    logger.info(
        "Uploaded %s to Gemini File API (name=%s), waiting for ACTIVE state...",
        media_path.name,
        uploaded.name,
    )

    elapsed = 0
    while uploaded.state.name != "ACTIVE":
        if elapsed >= FILE_POLL_TIMEOUT_SECONDS:
            raise RuntimeError(
                f"Gemini file {uploaded.name} did not become ACTIVE within "
                f"{FILE_POLL_TIMEOUT_SECONDS}s (state: {uploaded.state.name})"
            )
        time.sleep(FILE_POLL_INTERVAL_SECONDS)
        elapsed += FILE_POLL_INTERVAL_SECONDS
        uploaded = client.files.get(name=uploaded.name)
        logger.debug("File %s state: %s (waited %ds)", uploaded.name, uploaded.state.name, elapsed)

    logger.info("File %s is ACTIVE, proceeding with extraction", uploaded.name)
    return Part.from_uri(file_uri=uploaded.uri, mime_type=uploaded.mime_type)


def _media_path_list(media_paths: Path | Sequence[Path]) -> list[Path]:
    if isinstance(media_paths, Path):
        return [media_paths]
    return list(media_paths)


def generate_with_retry(
    client: genai.Client,
    *,
    model: str,
    contents: list,
    config: GenerateContentConfig,
    total_attempts: int,
):
    for attempt in range(total_attempts - 1):
        try:
            return client.models.generate_content(model=model, contents=contents, config=config)
        except (genai_errors.APIError, *RETRYABLE_TRANSPORT_ERRORS) as exc:
            if isinstance(exc, genai_errors.APIError) and exc.code not in RETRYABLE_STATUS_CODES:
                raise
            delay = RETRY_DELAYS_SECONDS[attempt]
            langfuse().create_event(
                name="retry-gemini-call",
                level="WARNING",
                status_message=describe_error(exc),
                metadata={"attempt": attempt + 1, "delay_seconds": delay},
            )
            logger.warning(
                "Gemini request failed (attempt %d/%d), retrying in %ds: %s: %s",
                attempt + 1,
                total_attempts,
                delay,
                type(exc).__name__,
                exc,
            )
            time.sleep(delay)
    return client.models.generate_content(model=model, contents=contents, config=config)


@dataclass(frozen=True)
class MentionsReply:
    payload: dict
    usage: dict[str, Any] | None


def request_mentions(paths: list[Path], *, model: str) -> MentionsReply:
    """Send the media and `EXTRACTION_PROMPT` to `model` and return the parsed mentions.

    Traced as the `extract-mentions` generation: the prompt and a description of each media
    file (never its bytes), the parsed reply, token usage, cost, and why it finished. An
    unusable reply raises `GeminiResponseError` and is recorded as an ERROR with its raw text.
    """
    settings = get_settings()
    client = get_gemini_client(settings)
    file_parts = [
        upload_to_gemini(client, media_path, use_vertexai=settings.gemini.use_vertexai)
        for media_path in paths
    ]
    with observe_step(
        "extract-mentions",
        as_type="generation",
        model=model,
        model_parameters={"temperature": EXTRACTION_TEMPERATURE},
        input=user_message(
            *(media_placeholder(_describe_media(path)) for path in paths),
            text_part(EXTRACTION_PROMPT),
        ),
        metadata={
            "prompt_version": EXTRACTION_PROMPT_VERSION,
            "media": [media_view(path) for path in paths],
        },
    ) as generation:
        response = generate_with_retry(
            client,
            model=model,
            contents=[*file_parts, EXTRACTION_PROMPT],
            config=GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=MENTION_SCHEMA,
                temperature=EXTRACTION_TEMPERATURE,
            ),
            total_attempts=settings.gemini.gemini_total_attempts,
        )
        record_gemini_reply(generation, model=model, response=response)
        generation.update(output=response.text)
        payload = parse_mentions_response(response)
        generation.update(output=payload)
    return MentionsReply(payload=payload, usage=gemini_usage(response))


def _describe_media(path: Path) -> str:
    view = media_view(path)
    return f"{view['mime_type']} {view['file']}, {view['bytes'] / 1024 / 1024:.1f} MB"


def extract_mentions_from_media(media_paths: Path | Sequence[Path]) -> dict:
    settings = get_settings()
    paths = _media_path_list(media_paths)
    if not paths:
        return {"mentions": []}
    check_media_size_limits(
        paths,
        max_file_bytes=settings.max_media_file_bytes,
        max_total_bytes=settings.max_media_total_bytes,
    )
    return request_mentions(paths, model=settings.gemini.gemini_model).payload


class GeminiResponseError(RuntimeError):
    """Gemini answered, but not with mentions the pipeline can use."""


def _finish_details(response) -> str:
    feedback = getattr(response, "prompt_feedback", None)
    block_reason = getattr(feedback, "block_reason", None)
    candidates = getattr(response, "candidates", None) or []
    finish_reason = getattr(candidates[0], "finish_reason", None) if candidates else None
    return f"block_reason={block_reason}, finish_reason={finish_reason}"


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_mentions_response(response) -> dict:
    """Return the `{"mentions": [...]}` payload, or raise GeminiResponseError.

    A blocked, truncated, or malformed reply must fail the source, which the user can
    retry, rather than be stored as a done source with no mentions: `sources` is a cache
    shared by everyone who saves the same Reel, and a done source is never extracted again.
    """
    text = response.text
    if not text:
        raise GeminiResponseError(f"Gemini returned no text ({_finish_details(response)})")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GeminiResponseError(
            f"Gemini returned invalid JSON ({_finish_details(response)}): {exc}"
        ) from exc

    mentions = payload.get("mentions") if isinstance(payload, dict) else None
    if not isinstance(mentions, list):
        raise GeminiResponseError("Gemini JSON has no mentions list")
    for mention in mentions:
        if not isinstance(mention, dict):
            raise GeminiResponseError("Gemini returned a mention that is not an object")
        for field in ("title", "author", "category", "location_hint"):
            if mention.get(field) is not None and not isinstance(mention[field], str):
                raise GeminiResponseError(f"Gemini returned a non-text mention {field}")
        confidence = mention.get("confidence")
        if confidence is not None and not _is_number(confidence):
            raise GeminiResponseError("Gemini returned a non-numeric mention confidence")
    return payload
