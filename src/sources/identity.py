from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from src.extraction.url import SourceUrlError, normalize_input_url


@dataclass(frozen=True)
class SourceIdentity:
    platform: str
    source_type: str
    external_id: str
    source_key: str
    canonical_url: str


def _instagram_identity(normalized_url: str) -> SourceIdentity:
    parts = urlsplit(normalized_url)
    segments = [segment for segment in parts.path.split("/") if segment]
    if len(segments) < 2:
        raise SourceUrlError(
            "Only public Instagram Reel and post URLs are supported",
            error_code="unsupported_source_kind",
        )

    raw_kind = segments[0].casefold()
    if raw_kind == "reel":
        source_type = "reel"
        path_kind = "reel"
    elif raw_kind == "p":
        source_type = "post"
        path_kind = "p"
    else:
        raise SourceUrlError(
            "Only public Instagram Reel and post URLs are supported",
            error_code="unsupported_source_kind",
        )

    external_id = segments[1]
    canonical_url = f"https://www.instagram.com/{path_kind}/{external_id}/"
    source_key = f"instagram:{source_type}:{external_id}"
    return SourceIdentity(
        platform="instagram",
        source_type=source_type,
        external_id=external_id,
        source_key=source_key,
        canonical_url=canonical_url,
    )


def identify_source(raw_url: str, *, require_https: bool = False) -> SourceIdentity:
    normalized_url = normalize_input_url(raw_url, require_https=require_https)
    parts = urlsplit(normalized_url)
    hostname = parts.hostname.casefold() if parts.hostname else ""
    if hostname in {"instagram.com", "www.instagram.com"}:
        return _instagram_identity(normalized_url)
    raise SourceUrlError("Only Instagram URLs are supported", error_code="unsupported_source_kind")
