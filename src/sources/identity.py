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


# URL path segment -> (source type, canonical path segment). The desktop Reels tab shows
# /reels/<code>/ for the same Reel a share link shows as /reel/<code>/.
_INSTAGRAM_PATH_KINDS = {"reel": ("reel", "reel"), "reels": ("reel", "reel"), "p": ("post", "p")}


def _instagram_identity(normalized_url: str) -> SourceIdentity:
    segments = [segment for segment in urlsplit(normalized_url).path.split("/") if segment]
    path_kind = segments[0].casefold() if len(segments) >= 2 else ""
    if path_kind not in _INSTAGRAM_PATH_KINDS:
        raise SourceUrlError(
            "Only public Instagram Reel and post URLs are supported",
            error_code="unsupported_source_kind",
        )

    source_type, canonical_path_kind = _INSTAGRAM_PATH_KINDS[path_kind]
    external_id = segments[1]
    canonical_url = f"https://www.instagram.com/{canonical_path_kind}/{external_id}/"
    source_key = f"instagram:{source_type}:{external_id}"
    return SourceIdentity(
        platform="instagram",
        source_type=source_type,
        external_id=external_id,
        source_key=source_key,
        canonical_url=canonical_url,
    )


def identify_source(raw_url: str, *, require_https: bool = False) -> SourceIdentity:
    # normalize_input_url already rejects every host except Instagram's.
    return _instagram_identity(normalize_input_url(raw_url, require_https=require_https))
