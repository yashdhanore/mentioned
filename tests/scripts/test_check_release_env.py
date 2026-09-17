from __future__ import annotations

import pytest

from scripts import check_release_env

VALID_ENV = {
    "APP_ENV": "production",
    "AUTH_MODE": "supabase",
    "AUTO_CREATE_TABLES": "false",
    "DOCS_ENABLED": "false",
    "SOURCE_REQUIRE_HTTPS": "true",
    "DATABASE_URL": "postgresql://mentioned_api:secret@example.supabase.co/postgres",
    "WORKER_DATABASE_URL": "postgresql://mentioned_worker:secret@example.supabase.co/postgres",
    "MIGRATION_DATABASE_URL": "postgresql://postgres:secret@example.supabase.co/postgres",
    "CORS_ALLOWED_ORIGINS": "https://mentioned.example",
    "TRUSTED_HOSTS": "mentioned-api.onrender.com",
    "SUPABASE_PROJECT_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "service-role-placeholder",
    "SUPABASE_JWT_AUDIENCE": "authenticated",
    "GEMINI_API_KEY": "gemini-placeholder",
}

GUARDRAIL_ENV_NAMES = {
    "MAX_JOB_CREATE_BURST_PER_MINUTE",
    "MAX_JOBS_CREATED_PER_DAY",
    "MAX_ACTIVE_JOBS_PER_USER",
    "MAX_MEDIA_DURATION_SECONDS",
    "MAX_MEDIA_FILE_BYTES",
    "MAX_MEDIA_TOTAL_BYTES",
    "MAX_MEDIA_VIDEO_COUNT",
    "GEMINI_TOTAL_ATTEMPTS",
}


@pytest.fixture
def valid_release_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in set(VALID_ENV) | GUARDRAIL_ENV_NAMES | {"GEMINI_USE_VERTEXAI"}:
        monkeypatch.delenv(name, raising=False)
    for name, value in VALID_ENV.items():
        monkeypatch.setenv(name, value)


def test_release_env_accepts_valid_default_guardrails(valid_release_env: None) -> None:
    assert check_release_env._check_release_env("1") == []


@pytest.mark.parametrize(
    ("name", "value", "expected"),
    [
        (
            "MAX_JOB_CREATE_BURST_PER_MINUTE",
            "0",
            "MAX_JOB_CREATE_BURST_PER_MINUTE must be between 1 and 10",
        ),
        (
            "MAX_JOB_CREATE_BURST_PER_MINUTE",
            "11",
            "MAX_JOB_CREATE_BURST_PER_MINUTE must be between 1 and 10",
        ),
        ("MAX_JOBS_CREATED_PER_DAY", "0", "MAX_JOBS_CREATED_PER_DAY must be between 1 and 100"),
        (
            "MAX_JOBS_CREATED_PER_DAY",
            "101",
            "MAX_JOBS_CREATED_PER_DAY must be between 1 and 100",
        ),
        (
            "MAX_ACTIVE_JOBS_PER_USER",
            "0",
            "MAX_ACTIVE_JOBS_PER_USER must be between 1 and 10",
        ),
        (
            "MAX_ACTIVE_JOBS_PER_USER",
            "11",
            "MAX_ACTIVE_JOBS_PER_USER must be between 1 and 10",
        ),
        (
            "MAX_MEDIA_DURATION_SECONDS",
            "301",
            "MAX_MEDIA_DURATION_SECONDS must be between 1 and 300",
        ),
        (
            "MAX_MEDIA_VIDEO_COUNT",
            "4",
            "MAX_MEDIA_VIDEO_COUNT must be between 1 and 3",
        ),
        (
            "GEMINI_TOTAL_ATTEMPTS",
            "4",
            "GEMINI_TOTAL_ATTEMPTS must be between 1 and 3",
        ),
        ("MAX_JOBS_CREATED_PER_DAY", "many", "MAX_JOBS_CREATED_PER_DAY must be an integer"),
    ],
)
def test_release_env_rejects_invalid_guardrail_overrides(
    valid_release_env: None,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
    expected: str,
) -> None:
    monkeypatch.setenv(name, value)

    assert expected in check_release_env._check_release_env("1")


def test_release_env_rejects_file_limit_above_total_limit(
    valid_release_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_MEDIA_FILE_BYTES", "10")
    monkeypatch.setenv("MAX_MEDIA_TOTAL_BYTES", "5")

    assert (
        "MAX_MEDIA_FILE_BYTES must be less than or equal to MAX_MEDIA_TOTAL_BYTES"
        in check_release_env._check_release_env("1")
    )
