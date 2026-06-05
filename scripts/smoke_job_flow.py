from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

import httpx


TERMINAL_STATUSES = {"done", "failed"}
SUCCESS_STATUSES = {"done"}


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


def _request_json_value(client: httpx.Client, method: str, path: str, **kwargs: Any) -> Any:
    response = client.request(method, path, **kwargs)
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise SmokeError(f"{method} {path} returned non-JSON {response.status_code}: {response.text[:500]}") from exc
    if response.status_code >= 400:
        raise SmokeError(f"{method} {path} returned {response.status_code}: {json.dumps(payload, default=str)}")
    return payload


def _request_json(client: httpx.Client, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    payload = _request_json_value(client, method, path, **kwargs)
    if not isinstance(payload, dict):
        raise SmokeError(f"{method} {path} returned JSON that was not an object")
    return payload


def _request_json_any_status(client: httpx.Client, method: str, path: str, **kwargs: Any) -> tuple[int, dict[str, Any]]:
    response = client.request(method, path, **kwargs)
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise SmokeError(f"{method} {path} returned non-JSON {response.status_code}: {response.text[:500]}") from exc
    if not isinstance(payload, dict):
        raise SmokeError(f"{method} {path} returned JSON that was not an object")
    return response.status_code, payload


def _assert_status(client: httpx.Client, method: str, path: str, expected_status: int, **kwargs: Any) -> dict[str, Any]:
    status_code, payload = _request_json_any_status(client, method, path, **kwargs)
    if status_code != expected_status:
        raise SmokeError(f"{method} {path} returned {status_code}, expected {expected_status}: {json.dumps(payload, default=str)}")
    return payload


def _saved_mentions_for_smoke(client: httpx.Client) -> list[dict[str, Any]]:
    payload = _request_json(client, "GET", "/v1/mentions", params={"limit": 100})
    items = payload.get("items")
    if not isinstance(items, list):
        raise SmokeError("GET /v1/mentions response did not include an items list")
    if any(not isinstance(item, dict) for item in items):
        raise SmokeError("GET /v1/mentions items must be JSON objects")
    return items


def _required(value: str | None, message: str) -> str:
    if value:
        return value
    raise SmokeError(message)


def run(args: argparse.Namespace) -> int:
    token = _required(args.token or _env("TOKEN") or _env("SUPABASE_ACCESS_TOKEN"), "Missing token. Pass --token or set TOKEN.")
    second_token = args.second_token or _env("SECOND_TOKEN") or _env("SUPABASE_SECOND_ACCESS_TOKEN")
    source_url = _required(args.source_url or _env("SOURCE_URL"), "Missing source URL. Pass --source-url or set SOURCE_URL.")

    headers = {"Authorization": f"Bearer {token}"}
    timeout = httpx.Timeout(args.request_timeout_seconds)
    with httpx.Client(base_url=args.api_base_url.rstrip("/"), headers=headers, timeout=timeout) as client:
        print(f"API: {args.api_base_url.rstrip('/')}")
        print(f"Source URL: {source_url}")

        create_payload = {"url": source_url}
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
            if status != last_status or args.verbose:
                print(f"poll: status={status}")
                last_status = status
            if status in TERMINAL_STATUSES:
                break
            time.sleep(args.poll_interval_seconds)
        else:
            raise SmokeError(f"Timed out after {args.timeout_seconds}s waiting for job {job_id}")

        _print_json("final job", job)
        mentions = job.get("mentions", [])
        if not isinstance(mentions, list):
            raise SmokeError("GET /v1/jobs/{job_id} response did not include a mentions list")
        _print_json("job mentions", {"count": len(mentions), "items": mentions})

        if args.require_mentions and not mentions:
            raise SmokeError("Job completed but returned no mentions")

        saved_mentions = _saved_mentions_for_smoke(client)
        _print_json("saved mentions", {"count": len(saved_mentions), "items": saved_mentions})

        job_mention_ids = {
            item.get("id")
            for item in mentions
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        saved_mention_ids = {
            item.get("id")
            for item in saved_mentions
            if isinstance(item.get("id"), str)
        }
        if job_mention_ids and not job_mention_ids.issubset(saved_mention_ids):
            missing = sorted(job_mention_ids - saved_mention_ids)
            raise SmokeError(f"Saved mentions did not include job mention IDs: {missing}")

        if second_token:
            second_headers = {"Authorization": f"Bearer {second_token}"}
            with httpx.Client(base_url=args.api_base_url.rstrip("/"), headers=second_headers, timeout=timeout) as second_client:
                _assert_status(second_client, "GET", f"/v1/jobs/{job_id}", 404)

                second_jobs = _request_json_value(second_client, "GET", "/v1/jobs")
                if not isinstance(second_jobs, list):
                    raise SmokeError("GET /v1/jobs response for second user was not a list")
                if any(isinstance(item, dict) and item.get("job_id") == job_id for item in second_jobs):
                    raise SmokeError("Second user job list included the first user's job")

                print("cross-user isolation checks passed")

        if job.get("status") not in SUCCESS_STATUSES:
            return 2
        return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit one backend job, poll it, then inspect saved mentions.")
    parser.add_argument("--api-base-url", default=_env("API_BASE_URL") or "http://127.0.0.1:8000")
    parser.add_argument("--token", default=None, help="Bearer access token. Defaults to TOKEN or SUPABASE_ACCESS_TOKEN.")
    parser.add_argument("--second-token", default=None, help="Second user's bearer token. Defaults to SECOND_TOKEN or SUPABASE_SECOND_ACCESS_TOKEN.")
    parser.add_argument("--source-url", default=None, help="Instagram Reel/post URL. Defaults to SOURCE_URL.")
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--request-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--require-mentions",
        action="store_true",
        help="Fail if the completed job returns no mentions. Use for Release 1 real-source smoke tests.",
    )
    return parser.parse_args()


def main() -> int:
    try:
        return run(parse_args())
    except (SmokeError, httpx.HTTPError) as exc:
        print(f"smoke failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
