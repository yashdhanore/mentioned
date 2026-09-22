from __future__ import annotations

import pytest

from src.config import BASE_DIR, get_settings

FULL_ENV = {
    "APP_ENV": "PRODUCTION",
    "DATABASE_URL": "postgresql://api:pw@example.supabase.co/postgres",
    "WORKER_DATABASE_URL": "postgresql://worker:pw@example.supabase.co/postgres",
    "AUTO_CREATE_TABLES": "false",
    "AUTH_MODE": "SUPABASE",
    "DEV_USER_ID": "11111111-1111-4111-8111-111111111111",
    "SUPABASE_PROJECT_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
    "SUPABASE_JWT_SECRET": "jwt-secret",
    "SUPABASE_JWT_AUDIENCE": "authenticated-aud",
    "DOCS_ENABLED": "false",
    "CORS_ALLOWED_ORIGINS": "https://a.example, https://b.example",
    "TRUSTED_HOSTS": "api.example.com, other.example.com",
    "SOURCE_REQUIRE_HTTPS": "true",
    "EXTRACTION_BACKEND": "GEMINI",
    "RELEVANCE_GATE_MODE": "ACTIVE",
    "WORKER_POLL_INTERVAL_SECONDS": "3.5",
    "WORKER_STALE_TIMEOUT_SECONDS": "600",
    "WORKER_QUEUE_VISIBILITY_TIMEOUT_SECONDS": "1200",
    "WORKER_QUEUE_MAX_POLL_SECONDS": "7",
    "WORKER_QUEUE_POLL_INTERVAL_MS": "250",
    "WORKER_QUEUE_MAX_DELIVERIES": "3",
    "WORKER_ID": "worker-test",
    "MEDIA_DOWNLOAD_TIMEOUT_SECONDS": "90",
    "MEDIA_DOWNLOAD_FORMAT": "mp4",
    "MAX_MEDIA_FILE_BYTES": "10485760",
    "MAX_MEDIA_TOTAL_BYTES": "20971520",
    "MAX_MEDIA_DURATION_SECONDS": "60",
    "MAX_MEDIA_VIDEO_COUNT": "2",
    "MEDIA_TRANSCODE_VIDEO_BITRATE": "900k",
    "MEDIA_TRANSCODE_AUDIO_BITRATE": "64k",
    "MAX_JOB_CREATE_BURST_PER_MINUTE": "2",
    "MAX_JOBS_CREATED_PER_DAY": "10",
    "MAX_ACTIVE_JOBS_PER_USER": "3",
    "GEMINI_API_KEY": "gemini-key",
    "GEMINI_MODEL": "gemini-test-model",
    "GEMINI_GATE_MODEL": "gemini-test-gate",
    "GEMINI_TOTAL_ATTEMPTS": "2",
    "GEMINI_TIMEOUT_SECONDS": "100",
    "GEMINI_USE_VERTEXAI": "true",
    "GEMINI_VERTEX_PROJECT": "vertex-project",
    "GEMINI_VERTEX_LOCATION": "us-central1",
    "GOOGLE_BOOKS_API_KEY": "books-key",
}

ALL_ENV_NAMES = set(FULL_ENV) | {
    "GOOGLE_GENAI_USE_VERTEXAI",
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch):
    for name in ALL_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _apply(monkeypatch: pytest.MonkeyPatch, overrides: dict[str, str]) -> None:
    for name, value in overrides.items():
        monkeypatch.setenv(name, value)


def test_settings_full_custom_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _apply(monkeypatch, FULL_ENV)

    settings = get_settings()

    assert settings.app_env == "production"
    assert settings.is_production is True
    assert settings.docs_enabled is False
    assert settings.cors_allowed_origins == ("https://a.example", "https://b.example")
    assert settings.trusted_hosts == ("api.example.com", "other.example.com")
    assert settings.source_require_https is True
    assert settings.extraction_backend == "gemini"
    assert settings.relevance_gate_mode == "active"
    assert settings.worker_poll_interval_seconds == 3.5
    assert settings.worker_stale_timeout_seconds == 600
    assert settings.worker_queue_visibility_timeout_seconds == 1200
    assert settings.worker_queue_max_poll_seconds == 7
    assert settings.worker_queue_poll_interval_ms == 250
    assert settings.worker_queue_max_deliveries == 3
    assert settings.worker_id == "worker-test"
    assert settings.media_download_timeout_seconds == 90
    assert settings.media_download_format == "mp4"
    assert settings.max_media_file_bytes == 10485760
    assert settings.max_media_total_bytes == 20971520
    assert settings.max_media_duration_seconds == 60
    assert settings.max_media_video_count == 2
    assert settings.media_transcode_video_bitrate == "900k"
    assert settings.media_transcode_audio_bitrate == "64k"
    assert settings.max_job_create_burst_per_minute == 2
    assert settings.max_jobs_created_per_day == 10
    assert settings.max_active_jobs_per_user == 3

    assert settings.database_url == FULL_ENV["DATABASE_URL"]
    assert settings.db.database_url == FULL_ENV["DATABASE_URL"]
    assert settings.worker_database_url == FULL_ENV["WORKER_DATABASE_URL"]
    assert settings.db.auto_create_tables is False

    assert settings.auth.auth_mode == "supabase"
    assert settings.auth.dev_user_id == "11111111-1111-4111-8111-111111111111"
    assert settings.auth.supabase_project_url == "https://example.supabase.co"
    assert settings.auth.supabase_service_role_key == "service-role-key"
    assert settings.auth.supabase_jwt_secret == "jwt-secret"
    assert settings.auth.supabase_jwt_audience == "authenticated-aud"

    assert settings.gemini.gemini_api_key == "gemini-key"
    assert settings.gemini.gemini_model == "gemini-test-model"
    assert settings.gemini.gemini_gate_model == "gemini-test-gate"
    assert settings.gemini.gemini_total_attempts == 2
    assert settings.gemini.gemini_timeout_seconds == 100
    assert settings.gemini.use_vertexai is True
    assert settings.gemini.vertex_project == "vertex-project"
    assert settings.gemini.vertex_location == "us-central1"

    assert settings.google_books.api_key == "books-key"


def test_settings_local_defaults() -> None:
    settings = get_settings()

    assert settings.app_env == "local"
    assert settings.is_production is False
    assert settings.docs_enabled is True
    assert settings.cors_allowed_origins == ()
    assert settings.trusted_hosts == ()
    assert settings.source_require_https is False
    assert settings.extraction_backend == "gemini"
    assert settings.relevance_gate_mode == "active"
    assert settings.worker_poll_interval_seconds == 2.0
    assert settings.worker_stale_timeout_seconds == 15 * 60
    assert settings.worker_queue_visibility_timeout_seconds == 30 * 60
    assert settings.worker_queue_max_poll_seconds == 5
    assert settings.worker_queue_poll_interval_ms == 100
    assert settings.worker_queue_max_deliveries == 5
    assert settings.worker_id == "worker-local"
    assert settings.media_download_timeout_seconds == 120
    assert settings.media_download_format is None
    assert settings.max_media_file_bytes == 50 * 1024 * 1024
    assert settings.max_media_total_bytes == 100 * 1024 * 1024
    assert settings.max_media_duration_seconds == 180
    assert settings.max_media_video_count == 1
    assert settings.media_transcode_video_bitrate == "1100k"
    assert settings.media_transcode_audio_bitrate == "96k"
    assert settings.max_job_create_burst_per_minute == 3
    assert settings.max_jobs_created_per_day == 25
    assert settings.max_active_jobs_per_user == 5

    assert settings.database_url == f"sqlite:///{BASE_DIR / 'app.db'}"
    assert settings.worker_database_url is None
    assert settings.db.auto_create_tables is True

    assert settings.auth.auth_mode == "dev"
    assert settings.auth.dev_user_id == "00000000-0000-4000-8000-000000000001"
    assert settings.auth.supabase_project_url is None
    assert settings.auth.supabase_jwt_audience == "authenticated"

    assert settings.gemini.gemini_model == "gemini-2.5-flash"
    assert settings.gemini.gemini_gate_model == "gemini-2.5-flash-lite"
    assert settings.gemini.gemini_total_attempts == 3
    assert settings.gemini.gemini_timeout_seconds == 120
    assert settings.gemini.use_vertexai is False
    assert settings.gemini.vertex_project is None
    assert settings.gemini.vertex_location == "global"

    assert settings.google_books.api_key is None


def test_settings_production_field_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_MODE", "supabase")
    monkeypatch.setenv("DATABASE_URL", "postgresql://api:pw@example.supabase.co/postgres")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://mentioned.example")
    monkeypatch.setenv("TRUSTED_HOSTS", "mentioned-api.onrender.com")
    monkeypatch.setenv("SUPABASE_PROJECT_URL", "https://example.supabase.co")

    settings = get_settings()

    assert settings.docs_enabled is False
    assert settings.source_require_https is True
    assert settings.db.auto_create_tables is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("off", False),
        ("banana", False),
        ("", False),
    ],
)
def test_settings_bool_parsing_matches_truthy_set(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: bool
) -> None:
    monkeypatch.setenv("DOCS_ENABLED", raw)

    assert get_settings().docs_enabled is expected


def test_settings_int_field_blank_string_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_MEDIA_VIDEO_COUNT", "  ")

    assert get_settings().max_media_video_count == 1


def test_settings_optional_field_blank_string_becomes_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "   ")

    assert get_settings().gemini.gemini_api_key is None


def test_settings_optional_field_strips_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "  key-with-padding  ")

    assert get_settings().gemini.gemini_api_key == "key-with-padding"


def test_settings_csv_field_blank_string_is_empty_tuple(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_MODE", "supabase")
    monkeypatch.setenv("DATABASE_URL", "postgresql://api:pw@example.supabase.co/postgres")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "   ")

    with pytest.raises(RuntimeError, match="CORS_ALLOWED_ORIGINS"):
        get_settings()


def test_settings_use_vertexai_falls_back_to_google_genai_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")

    assert get_settings().gemini.use_vertexai is True


def test_settings_use_vertexai_prefers_gemini_specific_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_USE_VERTEXAI", "false")
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")

    assert get_settings().gemini.use_vertexai is False


def test_settings_vertex_project_falls_back_to_google_cloud_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "fallback-project")

    assert get_settings().gemini.vertex_project == "fallback-project"


def test_settings_vertex_project_blank_falls_through_to_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A blank GEMINI_VERTEX_PROJECT is treated as unset, unlike a blank
    # GEMINI_USE_VERTEXAI (which is treated as an explicit false).
    monkeypatch.setenv("GEMINI_VERTEX_PROJECT", "")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "fallback-project")

    assert get_settings().gemini.vertex_project == "fallback-project"


def test_settings_vertex_location_falls_back_to_google_cloud_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "europe-west4")

    assert get_settings().gemini.vertex_location == "europe-west4"


def test_settings_gemini_model_set_blank_stays_blank_not_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Unlike optional/int fields, a raw getenv+strip field does not collapse
    # a blank value back to its default.
    monkeypatch.setenv("GEMINI_MODEL", "   ")

    assert get_settings().gemini.gemini_model == ""


@pytest.mark.parametrize(
    ("env", "match"),
    [
        ({"AUTH_MODE": "bogus"}, "Unsupported AUTH_MODE"),
        ({"EXTRACTION_BACKEND": "bogus"}, "Unsupported EXTRACTION_BACKEND"),
        ({"RELEVANCE_GATE_MODE": "bogus"}, "Unsupported RELEVANCE_GATE_MODE"),
        ({"WORKER_QUEUE_MAX_DELIVERIES": "0"}, "WORKER_QUEUE_MAX_DELIVERIES"),
        ({"MAX_MEDIA_DURATION_SECONDS": "301"}, "MAX_MEDIA_DURATION_SECONDS"),
        ({"MAX_MEDIA_DURATION_SECONDS": "0"}, "MAX_MEDIA_DURATION_SECONDS"),
        ({"MAX_MEDIA_FILE_BYTES": str(100 * 1024 * 1024 + 1)}, "MAX_MEDIA_FILE_BYTES"),
        ({"MAX_MEDIA_TOTAL_BYTES": str(150 * 1024 * 1024 + 1)}, "MAX_MEDIA_TOTAL_BYTES"),
        (
            {"MAX_MEDIA_FILE_BYTES": "200", "MAX_MEDIA_TOTAL_BYTES": "100"},
            "MAX_MEDIA_FILE_BYTES must be less than or equal to MAX_MEDIA_TOTAL_BYTES",
        ),
        ({"MAX_MEDIA_VIDEO_COUNT": "4"}, "MAX_MEDIA_VIDEO_COUNT"),
        ({"GEMINI_TOTAL_ATTEMPTS": "4"}, "GEMINI_TOTAL_ATTEMPTS"),
        ({"GEMINI_TIMEOUT_SECONDS": "301"}, "GEMINI_TIMEOUT_SECONDS"),
    ],
)
def test_settings_universal_validation_errors(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str], match: str
) -> None:
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(RuntimeError, match=match):
        get_settings()


PRODUCTION_BASE_ENV = {
    "APP_ENV": "production",
    "AUTH_MODE": "supabase",
    "DATABASE_URL": "postgresql://api:pw@example.supabase.co/postgres",
    "DOCS_ENABLED": "false",
    "SOURCE_REQUIRE_HTTPS": "true",
    "CORS_ALLOWED_ORIGINS": "https://mentioned.example",
    "TRUSTED_HOSTS": "mentioned-api.onrender.com",
    "SUPABASE_PROJECT_URL": "https://example.supabase.co",
}


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"AUTH_MODE": "dev"}, "Production requires AUTH_MODE=supabase"),
        ({"DATABASE_URL": "sqlite:///x.db"}, "Production requires a PostgreSQL DATABASE_URL"),
        ({"AUTO_CREATE_TABLES": "true"}, "Production requires AUTO_CREATE_TABLES=false"),
        ({"DOCS_ENABLED": "true"}, "Production requires DOCS_ENABLED=false"),
        ({"SOURCE_REQUIRE_HTTPS": "false"}, "Production requires SOURCE_REQUIRE_HTTPS=true"),
        ({"CORS_ALLOWED_ORIGINS": ""}, "Production requires at least one CORS_ALLOWED_ORIGINS"),
        (
            {"CORS_ALLOWED_ORIGINS": "http://mentioned.example"},
            "Production CORS_ALLOWED_ORIGINS must be HTTPS origins",
        ),
        ({"TRUSTED_HOSTS": ""}, "Production requires at least one TRUSTED_HOSTS"),
        ({"TRUSTED_HOSTS": "*"}, "Production TRUSTED_HOSTS must be explicit non-local hosts"),
        ({"SUPABASE_PROJECT_URL": ""}, "Production requires SUPABASE_PROJECT_URL"),
        ({"SUPABASE_JWT_AUDIENCE": ""}, "Production requires SUPABASE_JWT_AUDIENCE"),
    ],
)
def test_settings_production_validation_errors(
    monkeypatch: pytest.MonkeyPatch, overrides: dict[str, str], match: str
) -> None:
    env = {**PRODUCTION_BASE_ENV, **overrides}
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(RuntimeError, match=match):
        get_settings()


def test_settings_production_localhost_http_cors_origin_is_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = {**PRODUCTION_BASE_ENV, "CORS_ALLOWED_ORIGINS": "http://localhost:8082"}
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    # src/config.py's own runtime validator (distinct from the stricter
    # scripts/check_release_env.py release gate) still allows an explicit
    # localhost HTTP origin in production.
    get_settings()
