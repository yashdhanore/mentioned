from __future__ import annotations

import pytest
import respx
from httpx import Response

from extractor.stages import fetch_html as fetch_stage
from extractor.stages.fetch_html import fetch_html
from extractor.stages.normalize_url import SourceUrlError, normalize_supported_source_url


def test_normalize_supported_source_url_rejects_spoofed_and_non_http_urls() -> None:
    with pytest.raises(SourceUrlError) as spoofed:
        normalize_supported_source_url("https://instagram.com.evil.example/reel/abc/")
    assert spoofed.value.error_code == "unsupported_source_kind"

    with pytest.raises(SourceUrlError) as non_http:
        normalize_supported_source_url("file:///etc/passwd")
    assert non_http.value.error_code == "invalid_source_url"


@respx.mock
def test_fetch_html_revalidates_redirect_targets(monkeypatch) -> None:
    monkeypatch.setattr(fetch_stage, "_host_resolves_to_blocked_network", lambda hostname: False)
    respx.get("https://www.instagram.com/reel/abc/").mock(
        return_value=Response(302, headers={"location": "https://instagram.com.evil.example/reel/abc/"})
    )

    with pytest.raises(SourceUrlError) as error:
        fetch_html("https://www.instagram.com/reel/abc/")
    assert error.value.error_code == "unsupported_source_kind"


def test_fetch_html_blocks_private_resolution(monkeypatch) -> None:
    monkeypatch.setattr(fetch_stage, "_host_resolves_to_blocked_network", lambda hostname: True)

    with pytest.raises(SourceUrlError):
        fetch_html("https://www.instagram.com/reel/abc/")
