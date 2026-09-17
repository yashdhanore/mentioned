from __future__ import annotations

import pytest

from src.extraction.url import SourceUrlError
from src.sources.identity import identify_source


@pytest.mark.parametrize(
    ("raw_url", "source_key", "canonical_url"),
    [
        (
            "https://www.instagram.com/reel/ABC123/?igsh=abc&utm_source=share",
            "instagram:reel:ABC123",
            "https://www.instagram.com/reel/ABC123/",
        ),
        (
            "https://instagram.com/reel/ABC123",
            "instagram:reel:ABC123",
            "https://www.instagram.com/reel/ABC123/",
        ),
        (
            "https://www.instagram.com/p/POST123/?utm_medium=copy_link",
            "instagram:post:POST123",
            "https://www.instagram.com/p/POST123/",
        ),
    ],
)
def test_identify_instagram_sources(raw_url: str, source_key: str, canonical_url: str) -> None:
    identity = identify_source(raw_url, require_https=True)

    assert identity.platform == "instagram"
    assert identity.source_key == source_key
    assert identity.canonical_url == canonical_url


def test_identify_source_rejects_unsupported_url() -> None:
    with pytest.raises(SourceUrlError, match="Only Instagram URLs are supported"):
        identify_source("https://example.com/reel/ABC123/", require_https=True)


def test_identify_source_rejects_instagram_profile_path() -> None:
    with pytest.raises(
        SourceUrlError, match="Only public Instagram Reel and post URLs are supported"
    ):
        identify_source("https://www.instagram.com/someone/", require_https=True)
