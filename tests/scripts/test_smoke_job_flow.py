from __future__ import annotations

import argparse

import httpx
import pytest
import respx

from scripts import smoke_job_flow

API_BASE_URL = "https://api.example"


def _saved_source(*, items: list[dict[str, str]] | None = None) -> dict[str, object]:
    return {
        "id": "saved-source-1",
        "source_id": "source-1",
        "source_key": "instagram:reel:SHORTCODE",
        "status": "done",
        "source_url": "https://www.instagram.com/reel/SHORTCODE/",
        "created_at": "2026-06-22T12:00:00Z",
        "items": items if items is not None else [{"id": "item-1", "title": "Atomic Habits"}],
    }


def _args(*, require_items: bool, second_token: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(
        api_base_url=API_BASE_URL,
        token="user-a-token",
        second_token=second_token,
        source_url="https://www.instagram.com/reel/SHORTCODE/",
        poll_interval_seconds=0.01,
        timeout_seconds=1.0,
        request_timeout_seconds=5.0,
        verbose=False,
        require_items=require_items,
    )


@respx.mock
def test_smoke_job_flow_verifies_saved_source_items() -> None:
    saved_source = _saved_source()
    respx.post(f"{API_BASE_URL}/v1/saved-sources").mock(
        return_value=httpx.Response(202, json={**saved_source, "status": "processing", "items": []})
    )
    respx.get(f"{API_BASE_URL}/v1/saved-sources/saved-source-1").mock(
        return_value=httpx.Response(200, json=saved_source)
    )
    saved_sources_route = respx.get(f"{API_BASE_URL}/v1/saved-sources").mock(
        return_value=httpx.Response(200, json=[saved_source])
    )

    assert smoke_job_flow.run(_args(require_items=True)) == 0
    assert saved_sources_route.called
    assert saved_sources_route.calls.last.request.url.params["limit"] == "100"


@respx.mock
def test_smoke_job_flow_fails_when_saved_source_list_omits_submission() -> None:
    saved_source = _saved_source()
    respx.post(f"{API_BASE_URL}/v1/saved-sources").mock(
        return_value=httpx.Response(202, json={**saved_source, "status": "processing", "items": []})
    )
    respx.get(f"{API_BASE_URL}/v1/saved-sources/saved-source-1").mock(
        return_value=httpx.Response(200, json=saved_source)
    )
    respx.get(f"{API_BASE_URL}/v1/saved-sources").mock(return_value=httpx.Response(200, json=[]))

    with pytest.raises(
        smoke_job_flow.SmokeError,
        match="Saved source list did not include submitted saved source id",
    ):
        smoke_job_flow.run(_args(require_items=True))


@respx.mock
def test_smoke_job_flow_require_items_fails_when_saved_source_returns_no_items() -> None:
    saved_source = _saved_source(items=[])
    respx.post(f"{API_BASE_URL}/v1/saved-sources").mock(
        return_value=httpx.Response(202, json={**saved_source, "status": "processing"})
    )
    respx.get(f"{API_BASE_URL}/v1/saved-sources/saved-source-1").mock(
        return_value=httpx.Response(200, json=saved_source)
    )

    with pytest.raises(
        smoke_job_flow.SmokeError,
        match="Saved source completed but returned no extracted items",
    ):
        smoke_job_flow.run(_args(require_items=True))


@respx.mock
def test_smoke_job_flow_failed_saved_source_returns_status_code_two() -> None:
    saved_source = _saved_source(items=[])
    failed_source = {**saved_source, "status": "failed", "error_message": "Extraction failed"}
    respx.post(f"{API_BASE_URL}/v1/saved-sources").mock(
        return_value=httpx.Response(202, json={**saved_source, "status": "processing", "items": []})
    )
    respx.get(f"{API_BASE_URL}/v1/saved-sources/saved-source-1").mock(
        return_value=httpx.Response(200, json=failed_source)
    )

    assert smoke_job_flow.run(_args(require_items=True)) == 2


@respx.mock
def test_smoke_job_flow_checks_second_user_saved_source_isolation() -> None:
    saved_source = _saved_source()
    respx.post(f"{API_BASE_URL}/v1/saved-sources").mock(
        return_value=httpx.Response(202, json={**saved_source, "status": "processing", "items": []})
    )
    respx.get(f"{API_BASE_URL}/v1/saved-sources/saved-source-1").mock(
        side_effect=[
            httpx.Response(200, json=saved_source),
            httpx.Response(404, json={"error_code": "saved_source_not_found"}),
        ]
    )
    respx.get(f"{API_BASE_URL}/v1/saved-sources").mock(
        side_effect=[
            httpx.Response(200, json=[saved_source]),
            httpx.Response(200, json=[]),
        ]
    )

    assert smoke_job_flow.run(_args(require_items=False, second_token="user-b-token")) == 0
