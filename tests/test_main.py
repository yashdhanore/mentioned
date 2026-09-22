from __future__ import annotations

import pytest

import src.main as main_module
from src.config import Settings


def _settings_with_web_base_url(web_base_url: str | None) -> Settings:
    return main_module.settings.model_copy(update={"web_base_url": web_base_url})


@pytest.mark.parametrize("path", ["/privacy", "/support"])
async def test_redirects_to_web_when_web_base_url_configured(client, monkeypatch, path):
    monkeypatch.setattr(
        main_module, "settings", _settings_with_web_base_url("https://mentioned-web.onrender.com")
    )

    resp = await client.get(path)

    assert resp.status_code == 301
    assert resp.headers["location"] == f"https://mentioned-web.onrender.com{path}"


@pytest.mark.parametrize(
    ("path", "expected_title"),
    [
        ("/privacy", "Mentioned Privacy Policy"),
        ("/support", "Mentioned Support"),
    ],
)
async def test_serves_inline_page_when_web_base_url_not_configured(
    client, monkeypatch, path, expected_title
):
    monkeypatch.setattr(main_module, "settings", _settings_with_web_base_url(None))

    resp = await client.get(path)

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert f"<title>{expected_title}</title>" in resp.text
