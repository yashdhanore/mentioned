from __future__ import annotations

from collections.abc import Sequence
import json
import logging
import time
from pathlib import Path

from google import genai
from google.genai.types import GenerateContentConfig, HttpOptions, Part

from src.config import get_settings

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
    settings = get_settings()
    if settings.gemini.use_vertexai:
        if not settings.gemini.vertex_project:
            raise RuntimeError("GOOGLE_CLOUD_PROJECT is not configured for Vertex AI")
        return genai.Client(
            vertexai=True,
            project=settings.gemini.vertex_project,
            location=settings.gemini.vertex_location,
            http_options=HttpOptions(api_version="v1"),
        )

    api_key = settings.gemini.gemini_api_key
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    return genai.Client(api_key=api_key)


def _mime_type_for(path: Path) -> str:
    suffix = path.suffix.lower()
    mime_map = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
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
    logger.info("Uploaded %s to Gemini File API (name=%s), waiting for ACTIVE state...", media_path.name, uploaded.name)

    # Poll until the file transitions to ACTIVE
    elapsed = 0
    while uploaded.state.name != "ACTIVE":
        if elapsed >= FILE_POLL_TIMEOUT:
            raise RuntimeError(f"Gemini file {uploaded.name} did not become ACTIVE within {FILE_POLL_TIMEOUT}s (state: {uploaded.state.name})")
        time.sleep(FILE_POLL_INTERVAL)
        elapsed += FILE_POLL_INTERVAL
        uploaded = client.files.get(name=uploaded.name)
        logger.debug("File %s state: %s (waited %ds)", uploaded.name, uploaded.state.name, elapsed)

    logger.info("File %s is ACTIVE, proceeding with extraction", uploaded.name)
    return Part.from_uri(file_uri=uploaded.uri, mime_type=uploaded.mime_type)


MAX_RETRIES = 3
RETRY_DELAYS = [2, 5, 10]  # seconds between retries
RETRYABLE_STATUS_CODES = {429, 500, 503}


def _media_path_list(media_paths: Path | Sequence[Path]) -> list[Path]:
    if isinstance(media_paths, Path):
        return [media_paths]
    return list(media_paths)


def extract_mentions_from_media(media_paths: Path | Sequence[Path]) -> dict:
    settings = get_settings()
    client = _get_client()
    paths = _media_path_list(media_paths)
    if not paths:
        return {"mentions": []}
    file_parts = [
        upload_to_gemini(client, media_path, use_vertexai=settings.gemini.use_vertexai)
        for media_path in paths
    ]

    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=settings.gemini.gemini_model,
                contents=[*file_parts, EXTRACTION_PROMPT],
                config=GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=MENTION_SCHEMA,
                    temperature=0.1,
                ),
            )
            try:
                return json.loads(response.text)
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning("Failed to parse Gemini response: %s", exc)
                return {"mentions": []}
        except Exception as exc:
            last_exc = exc
            # Check if it's a retryable error (503, 429, etc.)
            exc_str = str(exc)
            is_retryable = any(str(code) in exc_str for code in RETRYABLE_STATUS_CODES)
            if not is_retryable or attempt == MAX_RETRIES - 1:
                raise
            delay = RETRY_DELAYS[attempt]
            logger.warning(
                "Gemini request failed (attempt %d/%d), retrying in %ds: %s",
                attempt + 1, MAX_RETRIES, delay, exc,
            )
            time.sleep(delay)

    raise last_exc  # unreachable, but satisfies type checker
