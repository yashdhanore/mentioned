from __future__ import annotations

import argparse
from getpass import getpass
import json
import os
from pathlib import Path
import sys
from typing import Any

from dotenv import load_dotenv
import httpx


BASE_DIR = Path(__file__).resolve().parents[1]


class TokenError(RuntimeError):
    pass


def _env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def _required(value: str | None, message: str) -> str:
    if value:
        return value
    raise TokenError(message)


def _password_from_args(args: argparse.Namespace) -> str:
    if args.password:
        return args.password
    env_password = _env("SUPABASE_PASSWORD")
    if env_password:
        return env_password
    return getpass("Supabase password: ")


def fetch_access_token(args: argparse.Namespace) -> dict[str, Any]:
    supabase_url = _required(
        args.supabase_url or _env("SUPABASE_PROJECT_URL"),
        "Missing Supabase URL. Pass --supabase-url or set SUPABASE_PROJECT_URL.",
    ).rstrip("/")
    anon_key = _required(
        args.anon_key or _env("SUPABASE_ANON_KEY"),
        "Missing Supabase anon key. Pass --anon-key or set SUPABASE_ANON_KEY.",
    )
    email = _required(
        args.email or _env("SUPABASE_EMAIL"),
        "Missing Supabase email. Pass --email or set SUPABASE_EMAIL.",
    )
    password = _password_from_args(args)
    if not password:
        raise TokenError("Missing Supabase password. Pass --password, set SUPABASE_PASSWORD, or enter it at the prompt.")

    response = httpx.post(
        f"{supabase_url}/auth/v1/token",
        params={"grant_type": "password"},
        headers={"apikey": anon_key, "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=args.timeout_seconds,
    )
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise TokenError(f"Supabase returned non-JSON {response.status_code}: {response.text[:500]}") from exc
    if response.status_code >= 400:
        raise TokenError(f"Supabase returned {response.status_code}: {json.dumps(payload, default=str)}")
    if not isinstance(payload, dict) or not isinstance(payload.get("access_token"), str):
        raise TokenError("Supabase response did not include access_token")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sign in to Supabase Auth and print a user access token.")
    parser.add_argument("--supabase-url", default=None, help="Defaults to SUPABASE_PROJECT_URL.")
    parser.add_argument("--anon-key", default=None, help="Defaults to SUPABASE_ANON_KEY.")
    parser.add_argument("--email", default=None, help="Defaults to SUPABASE_EMAIL.")
    parser.add_argument("--password", default=None, help="Defaults to SUPABASE_PASSWORD, otherwise prompts securely.")
    parser.add_argument("--json", action="store_true", help="Print the full Supabase Auth response as JSON.")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    load_dotenv(BASE_DIR / ".env")
    args = parse_args()
    try:
        payload = fetch_access_token(args)
    except (TokenError, httpx.HTTPError) as exc:
        print(f"token fetch failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(payload["access_token"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
