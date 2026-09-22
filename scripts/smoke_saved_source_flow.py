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


def _response_json(response: httpx.Response, method: str, path: str) -> Any:
    try:
        return response.json()
    except json.JSONDecodeError as exc:
        raise SmokeError(
            f"{method} {path} returned non-JSON {response.status_code}: {response.text[:500]}"
        ) from exc


def _request_json_value(client: httpx.Client, method: str, path: str, **kwargs: Any) -> Any:
    response = client.request(method, path, **kwargs)
    payload = _response_json(response, method, path)
    if response.status_code >= 400:
        raise SmokeError(
            f"{method} {path} returned {response.status_code}: {json.dumps(payload, default=str)}"
        )
    return payload


def _request_json(client: httpx.Client, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    payload = _request_json_value(client, method, path, **kwargs)
    if not isinstance(payload, dict):
        raise SmokeError(f"{method} {path} returned JSON that was not an object")
    return payload


def _assert_status(
    client: httpx.Client, method: str, path: str, expected_status: int, **kwargs: Any
) -> None:
    response = client.request(method, path, **kwargs)
    payload = _response_json(response, method, path)
    if response.status_code != expected_status:
        raise SmokeError(
            f"{method} {path} returned {response.status_code}, expected {expected_status}: "
            f"{json.dumps(payload, default=str)}"
        )


def _saved_sources_for_smoke(client: httpx.Client) -> list[dict[str, Any]]:
    payload = _request_json_value(client, "GET", "/v1/saved-sources", params={"limit": 100})
    if not isinstance(payload, list):
        raise SmokeError("GET /v1/saved-sources response was not a list")
    if any(not isinstance(item, dict) for item in payload):
        raise SmokeError("GET /v1/saved-sources items must be JSON objects")
    return payload


def _required(value: str | None, message: str) -> str:
    if value:
        return value
    raise SmokeError(message)


def run(args: argparse.Namespace) -> int:
    token = _required(
        args.token or _env("TOKEN") or _env("SUPABASE_ACCESS_TOKEN"),
        "Missing token. Pass --token or set TOKEN.",
    )
    second_token = args.second_token or _env("SECOND_TOKEN") or _env("SUPABASE_SECOND_ACCESS_TOKEN")
    source_url = _required(
        args.source_url or _env("SOURCE_URL"),
        "Missing source URL. Pass --source-url or set SOURCE_URL.",
    )

    headers = {"Authorization": f"Bearer {token}"}
    timeout = httpx.Timeout(args.request_timeout_seconds)
    with httpx.Client(
        base_url=args.api_base_url.rstrip("/"), headers=headers, timeout=timeout
    ) as client:
        print(f"API: {args.api_base_url.rstrip('/')}")
        print(f"Source URL: {source_url}")

        created = _request_json(client, "POST", "/v1/saved-sources", json={"url": source_url})
        _print_json("submitted saved source", created)

        saved_source_id = created.get("id")
        if not isinstance(saved_source_id, str) or not saved_source_id:
            raise SmokeError("POST /v1/saved-sources response did not include id")
        if not isinstance(created.get("status"), str):
            raise SmokeError("POST /v1/saved-sources response did not include status")

        deadline = time.monotonic() + args.timeout_seconds
        last_status = None
        saved_source: dict[str, Any] = created
        while time.monotonic() < deadline:
            saved_source = _request_json(client, "GET", f"/v1/saved-sources/{saved_source_id}")
            status = saved_source.get("status")
            if status != last_status or args.verbose:
                print(f"poll: status={status}")
                last_status = status
            if status in TERMINAL_STATUSES:
                break
            time.sleep(args.poll_interval_seconds)
        else:
            raise SmokeError(
                f"Timed out after {args.timeout_seconds}s waiting for saved source "
                f"{saved_source_id}"
            )

        _print_json("final saved source", saved_source)
        extracted_items = saved_source.get("items", [])
        if not isinstance(extracted_items, list):
            raise SmokeError("GET /v1/saved-sources/{id} response did not include an items list")
        _print_json("extracted items", {"count": len(extracted_items), "items": extracted_items})

        if saved_source.get("status") not in SUCCESS_STATUSES:
            return 2

        if args.require_items and not extracted_items:
            raise SmokeError("Saved source completed but returned no extracted items")

        saved_sources = _saved_sources_for_smoke(client)
        _print_json("saved sources", {"count": len(saved_sources), "items": saved_sources})

        if saved_source_id not in {item.get("id") for item in saved_sources}:
            raise SmokeError(
                f"Saved source list did not include submitted saved source id: {saved_source_id}"
            )

        if second_token:
            second_headers = {"Authorization": f"Bearer {second_token}"}
            with httpx.Client(
                base_url=args.api_base_url.rstrip("/"), headers=second_headers, timeout=timeout
            ) as second_client:
                _assert_status(second_client, "GET", f"/v1/saved-sources/{saved_source_id}", 404)

                second_saved_sources = _request_json_value(
                    second_client, "GET", "/v1/saved-sources"
                )
                if not isinstance(second_saved_sources, list):
                    raise SmokeError(
                        "GET /v1/saved-sources response for second user was not a list"
                    )
                if any(
                    isinstance(item, dict) and item.get("id") == saved_source_id
                    for item in second_saved_sources
                ):
                    raise SmokeError(
                        "Second user saved-source list included the first user's saved source"
                    )

                print("cross-user isolation checks passed")

        return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit one saved source, poll it, then inspect extracted items."
    )
    parser.add_argument("--api-base-url", default=_env("API_BASE_URL") or "http://127.0.0.1:8000")
    parser.add_argument(
        "--token",
        default=None,
        help="Bearer access token. Defaults to TOKEN or SUPABASE_ACCESS_TOKEN.",
    )
    parser.add_argument(
        "--second-token",
        default=None,
        help="Second user's bearer token. Defaults to SECOND_TOKEN or "
        "SUPABASE_SECOND_ACCESS_TOKEN.",
    )
    parser.add_argument(
        "--source-url", default=None, help="Instagram Reel/post URL. Defaults to SOURCE_URL."
    )
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--request-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--require-items",
        action="store_true",
        help="Fail if the completed saved source returns no extracted items. Use for Release 1 "
        "real-source smoke tests.",
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
