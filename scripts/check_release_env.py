from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv


REQUIRED_VALUES = {
    "APP_ENV": "production",
    "AUTH_MODE": "supabase",
    "AUTO_CREATE_TABLES": "false",
    "DOCS_ENABLED": "false",
    "SOURCE_REQUIRE_HTTPS": "true",
}


def _env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def _is_true(value: str | None) -> bool:
    return (value or "").strip().casefold() in {"1", "true", "yes", "on"}


def _is_local_hostname(hostname: str | None) -> bool:
    return hostname is not None and hostname.casefold() in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _is_postgres_url(value: str | None) -> bool:
    return bool(value) and (value.startswith("postgresql://") or value.startswith("postgresql+"))


def _invalid_origin(origin: str) -> bool:
    parsed = urlparse(origin)
    return parsed.scheme != "https" or not parsed.hostname or _is_local_hostname(parsed.hostname)


def _invalid_host(host: str) -> bool:
    if host == "*" or "://" in host:
        return True
    hostname = host.removeprefix("*.").split(":", 1)[0].strip("[]")
    return not hostname or _is_local_hostname(hostname)


def _csv(name: str) -> list[str]:
    value = _env(name)
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _check_release_env(worker_replicas: str | None) -> list[str]:
    errors: list[str] = []
    for name, expected in REQUIRED_VALUES.items():
        actual = _env(name)
        if actual is None or actual.casefold() != expected:
            errors.append(f"{name} must be {expected}")

    database_url = _env("DATABASE_URL")
    worker_database_url = _env("WORKER_DATABASE_URL")
    migration_database_url = _env("MIGRATION_DATABASE_URL")
    if not _is_postgres_url(database_url):
        errors.append("DATABASE_URL must be a PostgreSQL URL")
    if not _is_postgres_url(worker_database_url):
        errors.append("WORKER_DATABASE_URL must be a PostgreSQL URL")
    if not _is_postgres_url(migration_database_url):
        errors.append("MIGRATION_DATABASE_URL must be a PostgreSQL URL")
    if database_url and worker_database_url and database_url == worker_database_url:
        errors.append("DATABASE_URL and WORKER_DATABASE_URL must be distinct")
    if migration_database_url and migration_database_url in {database_url, worker_database_url}:
        errors.append("MIGRATION_DATABASE_URL must be distinct from runtime database URLs")

    origins = _csv("CORS_ALLOWED_ORIGINS")
    if not origins:
        errors.append("CORS_ALLOWED_ORIGINS must include at least one HTTPS origin")
    elif any(_invalid_origin(origin) for origin in origins):
        errors.append("CORS_ALLOWED_ORIGINS must contain only non-local HTTPS origins")

    hosts = _csv("TRUSTED_HOSTS")
    if not hosts:
        errors.append("TRUSTED_HOSTS must include at least one production host")
    elif any(_invalid_host(host) for host in hosts):
        errors.append("TRUSTED_HOSTS must contain only explicit non-local hosts")

    if not _env("SUPABASE_PROJECT_URL"):
        errors.append("SUPABASE_PROJECT_URL must be set")
    if not _env("SUPABASE_JWT_AUDIENCE"):
        errors.append("SUPABASE_JWT_AUDIENCE must be set")

    if _is_true(_env("GEMINI_USE_VERTEXAI")):
        if not (_env("GEMINI_VERTEX_PROJECT") or _env("GOOGLE_CLOUD_PROJECT")):
            errors.append("GEMINI_VERTEX_PROJECT or GOOGLE_CLOUD_PROJECT must be set for Vertex AI")
    elif not _env("GEMINI_API_KEY"):
        errors.append("GEMINI_API_KEY must be set when Vertex AI is disabled")

    if worker_replicas != "1":
        errors.append("worker replicas must be exactly 1 for beta")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate beta production release environment without printing secrets.")
    parser.add_argument("--env-file", default=".env", help="Environment file to load before validation.")
    parser.add_argument(
        "--worker-replicas",
        default=None,
        help="Expected deployed worker replica count. Defaults to WORKER_REPLICAS.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env_file = Path(args.env_file)
    if env_file.exists():
        load_dotenv(env_file)
    worker_replicas = args.worker_replicas or _env("WORKER_REPLICAS")
    errors = _check_release_env(worker_replicas)
    if errors:
        print("release environment check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("release environment check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
