from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_PARAMS = {"igsh", "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term"}


def normalize_input_url(raw_url: str) -> str:
    stripped = raw_url.strip()
    parts = urlsplit(stripped)
    if parts.scheme not in {"http", "https"}:
        raise ValueError("Only HTTP(S) URLs are supported")
    cleaned_path = parts.path or "/"
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
    ]
    cleaned_query = urlencode(query_pairs, doseq=True)
    return urlunsplit((parts.scheme, parts.netloc.lower(), cleaned_path, cleaned_query, ""))


def detect_source_kind(url: str) -> str:
    parts = urlsplit(url)
    host = parts.netloc.lower()
    path = parts.path.lower()
    if "instagram.com" in host and "/reel/" in path:
        return "instagram_reel"
    if "instagram.com" in host and "/p/" in path:
        return "instagram_post"
    return "unknown"
