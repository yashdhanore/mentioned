from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {"igsh", "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term"}
INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com"}


class SourceUrlError(ValueError):
    def __init__(self, message: str, *, error_code: str = "invalid_source_url") -> None:
        super().__init__(message)
        self.error_code = error_code


def normalize_input_url(raw_url: str, *, require_https: bool = False) -> str:
    stripped = raw_url.strip()
    parts = urlsplit(stripped)
    if parts.scheme not in {"http", "https"}:
        raise SourceUrlError("Only HTTP(S) URLs are supported")
    if require_https and parts.scheme != "https":
        raise SourceUrlError("Only HTTPS URLs are supported in this environment")
    hostname = parts.hostname.lower() if parts.hostname else ""
    if hostname not in INSTAGRAM_HOSTS:
        raise SourceUrlError(
            "Only Instagram URLs are supported", error_code="unsupported_source_kind"
        )
    cleaned_path = parts.path or "/"
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
    ]
    cleaned_query = urlencode(query_pairs, doseq=True)
    return urlunsplit((parts.scheme, hostname, cleaned_path, cleaned_query, ""))


def validate_instagram_url(raw_url: str, *, require_https: bool = False) -> str:
    normalized = normalize_input_url(raw_url, require_https=require_https)
    parts = urlsplit(normalized)
    path = parts.path.lower()
    if "/reel/" not in path and "/p/" not in path:
        raise SourceUrlError(
            "Only public Instagram Reel and post URLs are supported",
            error_code="unsupported_source_kind",
        )
    return normalized
