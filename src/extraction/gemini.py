from __future__ import annotations

import json
import logging
import time
from collections.abc import Sequence
from pathlib import Path

from google import genai
from google.genai import errors as genai_errors
from google.genai.types import GenerateContentConfig, Part

from src.config import get_settings
from src.extraction.gemini_client import get_gemini_client

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
Analyze this Instagram content (video with audio, or images).
Identify all books, products, and places that are explicitly mentioned, shown, or recommended.

Return JSON: {"mentions": [{"title": "...", "author": "...", "category": "book|product|place", "confidence": 0.0-1.0}]}

Rules:
- Only include items clearly and intentionally featured or recommended
- For books: include author if visible or spoken
- Confidence reflects how certain you are (visible cover = high, just mentioned in passing = lower)
- Do NOT include incidental background items, UI elements, or generic references
- A place is a specific location the creator recommends going to, such as a restaurant, shop, hotel, beach, landmark, or a destination pitched as a trip
- Do NOT list a place that only describes another item, such as the country or city a book is set in, where an author is from, or an on-screen label like "Turkey" next to a book
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
                },
                "required": ["title", "category", "confidence"],
            },
        }
    },
    "required": ["mentions"],
}

INLINE_SIZE_LIMIT = 20 * 1024 * 1024  # 20 MB
VERTEX_INLINE_SIZE_LIMIT = 100 * 1024 * 1024  # 100 MB


def _get_client() -> genai.Client:
    # scripts/compare_gemini_video_models.py (off limits for this change) imports this
    # zero-arg helper directly; keep it as a thin wrapper around the shared client builder.
    return get_gemini_client(get_settings())


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


FILE_POLL_INTERVAL = 2  # seconds between status checks
FILE_POLL_TIMEOUT = 120  # max seconds to wait for ACTIVE state


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

    # Poll until the file transitions to ACTIVE
    elapsed = 0
    while uploaded.state.name != "ACTIVE":
        if elapsed >= FILE_POLL_TIMEOUT:
            raise RuntimeError(
                f"Gemini file {uploaded.name} did not become ACTIVE within "
                f"{FILE_POLL_TIMEOUT}s (state: {uploaded.state.name})"
            )
        time.sleep(FILE_POLL_INTERVAL)
        elapsed += FILE_POLL_INTERVAL
        uploaded = client.files.get(name=uploaded.name)
        logger.debug("File %s state: %s (waited %ds)", uploaded.name, uploaded.state.name, elapsed)

    logger.info("File %s is ACTIVE, proceeding with extraction", uploaded.name)
    return Part.from_uri(file_uri=uploaded.uri, mime_type=uploaded.mime_type)


RETRY_DELAYS = [2, 5, 10]  # seconds between retries
RETRYABLE_STATUS_CODES = {429, 500, 503}


def _media_path_list(media_paths: Path | Sequence[Path]) -> list[Path]:
    if isinstance(media_paths, Path):
        return [media_paths]
    return list(media_paths)


def _check_size_limits(paths: Sequence[Path], *, max_file_bytes: int, max_total_bytes: int) -> None:
    total_bytes = 0
    for path in paths:
        file_bytes = path.stat().st_size
        if file_bytes > max_file_bytes:
            raise RuntimeError(
                f"Media file exceeds limit of {max_file_bytes} bytes "
                f"({path.name}: {file_bytes} bytes)"
            )
        total_bytes += file_bytes
    if total_bytes > max_total_bytes:
        raise RuntimeError(
            f"Media total exceeds limit of {max_total_bytes} bytes ({total_bytes} bytes)"
        )


def _generate_with_retry(
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
        except genai_errors.APIError as exc:
            if exc.code not in RETRYABLE_STATUS_CODES:
                raise
            delay = RETRY_DELAYS[attempt]
            logger.warning(
                "Gemini request failed (attempt %d/%d), retrying in %ds: %s",
                attempt + 1,
                total_attempts,
                delay,
                exc,
            )
            time.sleep(delay)
    return client.models.generate_content(model=model, contents=contents, config=config)


def extract_mentions_from_media(media_paths: Path | Sequence[Path]) -> dict:
    settings = get_settings()
    paths = _media_path_list(media_paths)
    if not paths:
        return {"mentions": []}
    _check_size_limits(
        paths,
        max_file_bytes=settings.max_media_file_bytes,
        max_total_bytes=settings.max_media_total_bytes,
    )
    client = get_gemini_client(settings)
    file_parts = [
        upload_to_gemini(client, media_path, use_vertexai=settings.gemini.use_vertexai)
        for media_path in paths
    ]

    response = _generate_with_retry(
        client,
        model=settings.gemini.gemini_model,
        contents=[*file_parts, EXTRACTION_PROMPT],
        config=GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=MENTION_SCHEMA,
            temperature=0.1,
        ),
        total_attempts=settings.gemini.gemini_total_attempts,
    )
    try:
        return json.loads(response.text)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("Failed to parse Gemini response: %s", exc)
        return {"mentions": []}
