from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx

from src.config import Settings, get_settings

try:
    from supabase import create_client
except ImportError:  # pragma: no cover - exercised only before dependencies are installed
    create_client = None


logger = logging.getLogger(__name__)

THUMBNAIL_STORAGE_BUCKET = "job-thumbnails"
MAX_THUMBNAIL_BYTES = 2 * 1024 * 1024
THUMBNAIL_DOWNLOAD_TIMEOUT_SECONDS = 10.0
THUMBNAIL_CACHE_SECONDS = 31_536_000
MAX_REDIRECTS = 5
ALLOWED_HOST_SUFFIXES = (".cdninstagram.com", ".fbcdn.net")
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


@dataclass(frozen=True)
class ThumbnailImage:
    data: bytes
    content_type: str
    extension: str


def _is_allowed_thumbnail_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError:
        return False

    if parsed.scheme != "https":
        return False
    if port not in (None, 443):
        return False
    hostname = (parsed.hostname or "").casefold()
    return any(
        hostname == suffix.removeprefix(".") or hostname.endswith(suffix)
        for suffix in ALLOWED_HOST_SUFFIXES
    )


def _response_content_type(response: httpx.Response) -> str | None:
    content_type = response.headers.get("content-type", "").split(";", 1)[0]
    content_type = content_type.strip().casefold()
    return content_type if content_type in ALLOWED_CONTENT_TYPES else None


def _download_response_body(response: httpx.Response) -> bytes | None:
    expected_size = response.headers.get("content-length")
    if expected_size and expected_size.isdecimal() and int(expected_size) > MAX_THUMBNAIL_BYTES:
        return None

    body = bytearray()
    for chunk in response.iter_bytes():
        body.extend(chunk)
        if len(body) > MAX_THUMBNAIL_BYTES:
            return None
    return bytes(body)


def _download_thumbnail(raw_url: str) -> ThumbnailImage | None:
    if not _is_allowed_thumbnail_url(raw_url):
        logger.info("Skipping thumbnail with unsupported URL: %s", raw_url)
        return None

    current_url = raw_url
    try:
        with httpx.Client(
            timeout=THUMBNAIL_DOWNLOAD_TIMEOUT_SECONDS,
            follow_redirects=False,
        ) as client:
            for _ in range(MAX_REDIRECTS + 1):
                if not _is_allowed_thumbnail_url(current_url):
                    logger.info("Skipping thumbnail redirect to unsupported URL: %s", current_url)
                    return None

                with client.stream("GET", current_url) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            return None
                        current_url = str(response.url.join(location))
                        continue

                    response.raise_for_status()
                    content_type = _response_content_type(response)
                    if not content_type:
                        logger.info(
                            "Skipping thumbnail with unsupported content type: %s",
                            response.headers.get("content-type", ""),
                        )
                        return None

                    data = _download_response_body(response)
                    if not data:
                        logger.info("Skipping empty or oversized thumbnail")
                        return None
                    return ThumbnailImage(
                        data=data,
                        content_type=content_type,
                        extension=ALLOWED_CONTENT_TYPES[content_type],
                    )
    except httpx.HTTPError as exc:
        logger.warning("Failed to download thumbnail %s: %s", raw_url, exc)
        return None

    logger.info("Skipping thumbnail after too many redirects")
    return None


def _storage_path(source_id: UUID, extension: str) -> str:
    # The path still says "jobs" because changing it would orphan thumbnails
    # already uploaded to Supabase Storage under the old layout.
    return f"users/{source_id}/jobs/{source_id}/thumbnail{extension}"


def _public_url(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("publicUrl", "public_url", "signedURL", "signed_url"):
            url = value.get(key)
            if isinstance(url, str):
                return url
    return None


def store_source_thumbnail(
    raw_thumbnail_url: str | None,
    *,
    source_id: UUID,
    settings: Settings | None = None,
) -> str | None:
    if not raw_thumbnail_url:
        return None

    settings = settings or get_settings()
    supabase_url = settings.auth.supabase_project_url
    service_role_key = settings.auth.supabase_service_role_key
    if not supabase_url or not service_role_key:
        logger.info("Skipping thumbnail storage because Supabase Storage is not configured")
        return None
    if create_client is None:
        logger.warning("Skipping thumbnail storage because supabase-py is not installed")
        return None

    image = _download_thumbnail(raw_thumbnail_url)
    if image is None:
        return None

    path = _storage_path(source_id, image.extension)
    try:
        client = create_client(supabase_url, service_role_key)
        bucket = client.storage.from_(THUMBNAIL_STORAGE_BUCKET)
        bucket.upload(
            path=path,
            file=image.data,
            file_options={
                "cache-control": str(THUMBNAIL_CACHE_SECONDS),
                "content-type": image.content_type,
                "upsert": "false",
            },
        )
        return _public_url(bucket.get_public_url(path))
    except Exception as exc:
        logger.warning("Failed to store thumbnail for source %s: %s", source_id, exc)
        return None
