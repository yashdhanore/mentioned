from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import sys
import time
from typing import Any
from uuid import uuid4

import httpx


TERMINAL_STATUSES = {"succeeded", "partial", "failed", "canceled", "expired"}
SUCCESS_STATUSES = {"succeeded", "partial"}


class SmokeError(RuntimeError):
    pass


def _env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def _print_json(label: str, payload: Any) -> None:
    print(f"\n== {label} ==")
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _request_json(client: httpx.Client, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    response = client.request(method, path, **kwargs)
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise SmokeError(f"{method} {path} returned non-JSON {response.status_code}: {response.text[:500]}") from exc
    if response.status_code >= 400:
        raise SmokeError(f"{method} {path} returned {response.status_code}: {json.dumps(payload, default=str)}")
    if not isinstance(payload, dict):
        raise SmokeError(f"{method} {path} returned JSON that was not an object")
    return payload


def _required(value: str | None, message: str) -> str:
    if value:
        return value
    raise SmokeError(message)


def _fetch_mentions_for_job(client: httpx.Client, job_id: str) -> list[dict[str, Any]]:
    mentions: list[dict[str, Any]] = []
    cursor: str | None = None
    for _ in range(10):
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        payload = _request_json(client, "GET", "/v1/mentions", params=params)
        items = payload.get("items", [])
        if not isinstance(items, list):
            raise SmokeError("GET /v1/mentions response did not include an items list")
        mentions.extend(item for item in items if isinstance(item, dict) and item.get("source_job_id") == job_id)
        cursor = payload.get("next_cursor")
        if not cursor:
            break
    return mentions


def run(args: argparse.Namespace) -> int:
    token = _required(args.token or _env("TOKEN") or _env("SUPABASE_ACCESS_TOKEN"), "Missing token. Pass --token or set TOKEN.")
    source_url = _required(args.source_url or _env("SOURCE_URL"), "Missing source URL. Pass --source-url or set SOURCE_URL.")
    idempotency_key = args.idempotency_key or f"smoke-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"

    headers = {"Authorization": f"Bearer {token}"}
    timeout = httpx.Timeout(args.request_timeout_seconds)
    with httpx.Client(base_url=args.api_base_url.rstrip("/"), headers=headers, timeout=timeout) as client:
        print(f"API: {args.api_base_url.rstrip('/')}")
        print(f"Source URL: {source_url}")
        print(f"Idempotency key: {idempotency_key}")

        create_payload = {"url": source_url, "idempotency_key": idempotency_key}
        created = _request_json(client, "POST", "/v1/jobs", json=create_payload)
        _print_json("submitted job", created)

        job_id = created.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            raise SmokeError("POST /v1/jobs response did not include job_id")

        deadline = time.monotonic() + args.timeout_seconds
        last_status = None
        job: dict[str, Any] = created
        while time.monotonic() < deadline:
            job = _request_json(client, "GET", f"/v1/jobs/{job_id}")
            status = job.get("status")
            stage = job.get("current_stage")
            progress = job.get("progress")
            if status != last_status or args.verbose:
                print(f"poll: status={status} stage={stage} progress={progress}")
                last_status = status
            if status in TERMINAL_STATUSES:
                break
            time.sleep(args.poll_interval_seconds)
        else:
            raise SmokeError(f"Timed out after {args.timeout_seconds}s waiting for job {job_id}")

        _print_json("final job", job)
        result = _request_json(client, "GET", f"/v1/jobs/{job_id}/result")
        _print_json("job result", result)

        mentions = _fetch_mentions_for_job(client, job_id)
        _print_json("saved mentions for job", {"count": len(mentions), "items": mentions})

        if job.get("status") not in SUCCESS_STATUSES:
            return 2
        return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit one backend job, poll it, then fetch result and saved mentions.")
    parser.add_argument("--api-base-url", default=_env("API_BASE_URL") or "http://127.0.0.1:8000")
    parser.add_argument("--token", default=None, help="Bearer access token. Defaults to TOKEN or SUPABASE_ACCESS_TOKEN.")
    parser.add_argument("--source-url", default=None, help="Instagram Reel/post URL. Defaults to SOURCE_URL.")
    parser.add_argument("--idempotency-key", default=None)
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--request-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    try:
        return run(parse_args())
    except (SmokeError, httpx.HTTPError) as exc:
        print(f"smoke failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
