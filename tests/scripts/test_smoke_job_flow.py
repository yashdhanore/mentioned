from __future__ import annotations

import argparse

import httpx
import pytest
import respx

from scripts import smoke_job_flow


API_BASE_URL = "https://api.example"


def _args(*, require_mentions: bool) -> argparse.Namespace:
    return argparse.Namespace(
        api_base_url=API_BASE_URL,
        token="user-a-token",
        second_token=None,
        source_url="https://www.instagram.com/reel/SHORTCODE/",
        poll_interval_seconds=0.01,
        timeout_seconds=1.0,
        request_timeout_seconds=5.0,
        verbose=False,
        require_mentions=require_mentions,
    )


@respx.mock
def test_smoke_job_flow_verifies_saved_mentions() -> None:
    respx.post(f"{API_BASE_URL}/v1/jobs").mock(
        return_value=httpx.Response(200, json={"job_id": "job-1", "status": "pending"})
    )
    respx.get(f"{API_BASE_URL}/v1/jobs/job-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "job_id": "job-1",
                "status": "done",
                "mentions": [{"id": "mention-1", "title": "Atomic Habits"}],
            },
        )
    )
    mentions_route = respx.get(f"{API_BASE_URL}/v1/mentions").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [{"id": "mention-1", "title": "Atomic Habits"}],
                "next_cursor": None,
            },
        )
    )

    assert smoke_job_flow.run(_args(require_mentions=True)) == 0
    assert mentions_route.called
    assert mentions_route.calls.last.request.url.params["limit"] == "100"


@respx.mock
def test_smoke_job_flow_fails_when_saved_mentions_omit_job_mentions() -> None:
    respx.post(f"{API_BASE_URL}/v1/jobs").mock(
        return_value=httpx.Response(200, json={"job_id": "job-1", "status": "pending"})
    )
    respx.get(f"{API_BASE_URL}/v1/jobs/job-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "job_id": "job-1",
                "status": "done",
                "mentions": [{"id": "mention-1", "title": "Atomic Habits"}],
            },
        )
    )
    respx.get(f"{API_BASE_URL}/v1/mentions").mock(
        return_value=httpx.Response(200, json={"items": [], "next_cursor": None})
    )

    with pytest.raises(
        smoke_job_flow.SmokeError,
        match="Saved mentions did not include job mention IDs",
    ):
        smoke_job_flow.run(_args(require_mentions=True))


@respx.mock
def test_smoke_job_flow_require_mentions_fails_when_job_returns_no_mentions() -> None:
    respx.post(f"{API_BASE_URL}/v1/jobs").mock(
        return_value=httpx.Response(200, json={"job_id": "job-1", "status": "pending"})
    )
    respx.get(f"{API_BASE_URL}/v1/jobs/job-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "job_id": "job-1",
                "status": "done",
                "mentions": [],
            },
        )
    )

    with pytest.raises(
        smoke_job_flow.SmokeError,
        match="Job completed but returned no mentions",
    ):
        smoke_job_flow.run(_args(require_mentions=True))
