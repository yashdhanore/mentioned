from __future__ import annotations

from extractor.clients.yt_dlp import probe_url


def probe_media(url: str) -> dict:
    return probe_url(url)

