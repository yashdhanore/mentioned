from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from pydantic import AliasChoices, BeforeValidator, Field, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
SUPPORTED_AUTH_MODES = {"dev", "supabase"}
SUPPORTED_EXTRACTION_BACKENDS = {"gemini", "local"}
SUPPORTED_RELEVANCE_GATE_MODES = {"off", "shadow", "active"}
HARD_MAX_MEDIA_DURATION_SECONDS = 300
HARD_MAX_MEDIA_FILE_BYTES = 100 * 1024 * 1024
HARD_MAX_MEDIA_TOTAL_BYTES = 150 * 1024 * 1024
HARD_MAX_MEDIA_VIDEO_COUNT = 3
HARD_MAX_GEMINI_TOTAL_ATTEMPTS = 3
HARD_MAX_GEMINI_TIMEOUT_SECONDS = 300

_TRUTHY = {"1", "true", "yes", "on"}
_ENV_CONFIG = SettingsConfigDict(
    env_file=None,
    case_sensitive=False,
    frozen=True,
    extra="ignore",
    populate_by_name=True,
)


def _parse_bool(value: Any) -> Any:
    # A present-but-blank env var is an explicit false, not "unset".
    if not isinstance(value, str):
        return value
    return value.strip().casefold() in _TRUTHY


def _strip(value: Any) -> Any:
    return value.strip() if isinstance(value, str) else value


def _casefold(value: Any) -> Any:
    return value.strip().casefold() if isinstance(value, str) else value


def _blank_as_none(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    return text or None


def _blank_as_none_no_trailing_slash(value: Any) -> Any:
    text = _blank_as_none(value)
    return text.rstrip("/") if isinstance(text, str) else text


def _blank_as(default: Any):
    def _parse(value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return default
        return value

    return _parse


def _parse_csv(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if not value.strip():
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _first_nonblank_env(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return None


EnvBool = Annotated[bool, BeforeValidator(_parse_bool)]
StrippedStr = Annotated[str, BeforeValidator(_strip)]
CasefoldStr = Annotated[str, BeforeValidator(_casefold)]
OptionalEnvStr = Annotated[str | None, BeforeValidator(_blank_as_none)]
OptionalEnvUrl = Annotated[str | None, BeforeValidator(_blank_as_none_no_trailing_slash)]
EnvCsv = Annotated[tuple[str, ...], NoDecode, BeforeValidator(_parse_csv)]

DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"
GeminiModelName = Annotated[StrippedStr, BeforeValidator(_blank_as(DEFAULT_GEMINI_MODEL))]


class DBConfig(BaseSettings):
    model_config = _ENV_CONFIG

    database_url: str = Field(default_factory=lambda: f"sqlite:///{BASE_DIR / 'app.db'}")
    worker_database_url: OptionalEnvStr = None
    auto_create_tables: EnvBool = True


class AuthConfig(BaseSettings):
    model_config = _ENV_CONFIG

    auth_mode: CasefoldStr = "dev"
    dev_user_id: StrippedStr = "00000000-0000-4000-8000-000000000001"
    supabase_project_url: OptionalEnvStr = None
    supabase_service_role_key: OptionalEnvStr = None
    supabase_jwt_secret: OptionalEnvStr = None
    supabase_jwt_audience: StrippedStr = "authenticated"


class GeminiConfig(BaseSettings):
    model_config = _ENV_CONFIG

    gemini_api_key: OptionalEnvStr = None
    gemini_model: GeminiModelName = DEFAULT_GEMINI_MODEL
    gemini_gate_model: GeminiModelName = DEFAULT_GEMINI_MODEL
    gemini_total_attempts: Annotated[int, BeforeValidator(_blank_as(3))] = 3
    gemini_timeout_seconds: Annotated[int, BeforeValidator(_blank_as(120))] = 120
    use_vertexai: EnvBool = Field(
        default=False,
        validation_alias=AliasChoices("GEMINI_USE_VERTEXAI", "GOOGLE_GENAI_USE_VERTEXAI"),
    )
    vertex_project: str | None = None
    vertex_location: str = "global"

    @model_validator(mode="after")
    def _apply_vertex_fallbacks(self) -> GeminiConfig:
        # A blank GEMINI_* var falls through to its GOOGLE_CLOUD_* counterpart.
        # AliasChoices stops at the first *present* var, so it cannot express
        # this. A value passed to the constructor is left alone.
        if "vertex_project" not in self.model_fields_set:
            project = _first_nonblank_env("GEMINI_VERTEX_PROJECT", "GOOGLE_CLOUD_PROJECT")
            object.__setattr__(self, "vertex_project", project)
        if "vertex_location" not in self.model_fields_set:
            location = (
                _first_nonblank_env("GEMINI_VERTEX_LOCATION", "GOOGLE_CLOUD_LOCATION") or "global"
            )
            object.__setattr__(self, "vertex_location", location)
        return self


class GoogleBooksConfig(BaseSettings):
    model_config = _ENV_CONFIG

    api_key: OptionalEnvStr = Field(default=None, validation_alias="GOOGLE_BOOKS_API_KEY")


class LangfuseConfig(BaseSettings):
    """Langfuse Cloud credentials. Tracing is on only when both keys are set; see
    `src/observability.py`."""

    model_config = _ENV_CONFIG

    public_key: OptionalEnvStr = Field(default=None, validation_alias="LANGFUSE_PUBLIC_KEY")
    secret_key: OptionalEnvStr = Field(default=None, validation_alias="LANGFUSE_SECRET_KEY")
    # Langfuse Cloud EU. The US region is https://us.cloud.langfuse.com.
    base_url: Annotated[str, BeforeValidator(_blank_as("https://cloud.langfuse.com"))] = Field(
        default="https://cloud.langfuse.com", validation_alias="LANGFUSE_BASE_URL"
    )

    @property
    def enabled(self) -> bool:
        return bool(self.public_key and self.secret_key)


class Settings(BaseSettings):
    model_config = _ENV_CONFIG

    app_name: str = "Mentioned Backend"
    app_env: CasefoldStr = "local"
    web_base_url: OptionalEnvUrl = None
    docs_enabled: EnvBool = True
    cors_allowed_origins: EnvCsv = ()
    trusted_hosts: EnvCsv = ()
    source_require_https: EnvBool = False
    extraction_backend: CasefoldStr = "gemini"
    relevance_gate_mode: CasefoldStr = "active"

    # Worker
    worker_poll_interval_seconds: Annotated[float, BeforeValidator(_blank_as(2.0))] = 2.0
    worker_stale_timeout_seconds: Annotated[int, BeforeValidator(_blank_as(15 * 60))] = 15 * 60
    worker_queue_visibility_timeout_seconds: Annotated[int, BeforeValidator(_blank_as(30 * 60))] = (
        30 * 60
    )
    worker_queue_max_poll_seconds: Annotated[int, BeforeValidator(_blank_as(5))] = 5
    worker_queue_poll_interval_ms: Annotated[int, BeforeValidator(_blank_as(100))] = 100
    worker_queue_max_deliveries: Annotated[int, BeforeValidator(_blank_as(5))] = 5
    worker_id: StrippedStr = "worker-local"

    # Media download limits
    media_download_timeout_seconds: Annotated[int, BeforeValidator(_blank_as(120))] = 120
    media_download_format: OptionalEnvStr = None
    max_media_file_bytes: Annotated[int, BeforeValidator(_blank_as(50 * 1024 * 1024))] = (
        50 * 1024 * 1024
    )
    max_media_total_bytes: Annotated[int, BeforeValidator(_blank_as(100 * 1024 * 1024))] = (
        100 * 1024 * 1024
    )
    max_media_duration_seconds: Annotated[int, BeforeValidator(_blank_as(180))] = 180
    max_media_video_count: Annotated[int, BeforeValidator(_blank_as(1))] = 1
    media_transcode_video_bitrate: StrippedStr = "1100k"
    media_transcode_audio_bitrate: StrippedStr = "96k"

    # Rate limits
    max_job_create_burst_per_minute: Annotated[int, BeforeValidator(_blank_as(3))] = 3
    max_jobs_created_per_day: Annotated[int, BeforeValidator(_blank_as(25))] = 25
    max_active_jobs_per_user: Annotated[int, BeforeValidator(_blank_as(5))] = 5

    # Sub-configs
    db: DBConfig = Field(default_factory=DBConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    google_books: GoogleBooksConfig = Field(default_factory=GoogleBooksConfig)
    langfuse: LangfuseConfig = Field(default_factory=LangfuseConfig)

    @model_validator(mode="after")
    def _apply_app_env_defaults(self) -> Settings:
        # docs_enabled, source_require_https, and db.auto_create_tables all
        # default differently depending on app_env (and, for auto_create_tables,
        # database_url); only fix them up when nothing (env or an explicit
        # constructor kwarg) actually set them, so an explicit value always wins.
        if "docs_enabled" not in self.model_fields_set:
            object.__setattr__(self, "docs_enabled", self.app_env != "production")
        if "source_require_https" not in self.model_fields_set:
            object.__setattr__(self, "source_require_https", self.app_env == "production")
        if "auto_create_tables" not in self.db.model_fields_set:
            object.__setattr__(
                self.db,
                "auto_create_tables",
                self.db.database_url.startswith("sqlite") and self.app_env != "production",
            )
        return self

    @property
    def database_url(self) -> str:
        return self.db.database_url

    @property
    def worker_database_url(self) -> str | None:
        return self.db.worker_database_url

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


def _is_postgres_url(database_url: str) -> bool:
    return database_url.startswith("postgresql://") or database_url.startswith("postgresql+")


def _is_local_hostname(hostname: str | None) -> bool:
    return hostname is not None and hostname.casefold() in {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
    }


def _is_invalid_production_origin(origin: str) -> bool:
    if origin == "*":
        return True
    parsed = urlparse(origin)
    if not parsed.scheme or not parsed.hostname:
        return True
    if _is_local_hostname(parsed.hostname):
        return parsed.scheme != "http"
    return parsed.scheme != "https"


def _is_invalid_production_host(host: str) -> bool:
    if host == "*" or "://" in host:
        return True
    hostname = host.removeprefix("*.").split(":", 1)[0].strip("[]")
    return not hostname or _is_local_hostname(hostname)


def validate_settings(settings: Settings) -> None:
    if settings.auth.auth_mode not in SUPPORTED_AUTH_MODES:
        raise RuntimeError(f"Unsupported AUTH_MODE: {settings.auth.auth_mode}")
    if settings.extraction_backend not in SUPPORTED_EXTRACTION_BACKENDS:
        raise RuntimeError(f"Unsupported EXTRACTION_BACKEND: {settings.extraction_backend}")
    if settings.relevance_gate_mode not in SUPPORTED_RELEVANCE_GATE_MODES:
        raise RuntimeError(f"Unsupported RELEVANCE_GATE_MODE: {settings.relevance_gate_mode}")
    if settings.worker_queue_max_deliveries < 1:
        raise RuntimeError("WORKER_QUEUE_MAX_DELIVERIES must be at least 1")
    if not 1 <= settings.max_media_duration_seconds <= HARD_MAX_MEDIA_DURATION_SECONDS:
        raise RuntimeError(
            f"MAX_MEDIA_DURATION_SECONDS must be between 1 and {HARD_MAX_MEDIA_DURATION_SECONDS}"
        )
    if not 1 <= settings.max_media_file_bytes <= HARD_MAX_MEDIA_FILE_BYTES:
        raise RuntimeError(
            f"MAX_MEDIA_FILE_BYTES must be between 1 and {HARD_MAX_MEDIA_FILE_BYTES}"
        )
    if not 1 <= settings.max_media_total_bytes <= HARD_MAX_MEDIA_TOTAL_BYTES:
        raise RuntimeError(
            f"MAX_MEDIA_TOTAL_BYTES must be between 1 and {HARD_MAX_MEDIA_TOTAL_BYTES}"
        )
    if settings.max_media_file_bytes > settings.max_media_total_bytes:
        raise RuntimeError(
            "MAX_MEDIA_FILE_BYTES must be less than or equal to MAX_MEDIA_TOTAL_BYTES"
        )
    if not 1 <= settings.max_media_video_count <= HARD_MAX_MEDIA_VIDEO_COUNT:
        raise RuntimeError(
            f"MAX_MEDIA_VIDEO_COUNT must be between 1 and {HARD_MAX_MEDIA_VIDEO_COUNT}"
        )
    if not 1 <= settings.gemini.gemini_total_attempts <= HARD_MAX_GEMINI_TOTAL_ATTEMPTS:
        raise RuntimeError(
            f"GEMINI_TOTAL_ATTEMPTS must be between 1 and {HARD_MAX_GEMINI_TOTAL_ATTEMPTS}"
        )
    if not 1 <= settings.gemini.gemini_timeout_seconds <= HARD_MAX_GEMINI_TIMEOUT_SECONDS:
        raise RuntimeError(
            f"GEMINI_TIMEOUT_SECONDS must be between 1 and {HARD_MAX_GEMINI_TIMEOUT_SECONDS}"
        )
    if not settings.is_production:
        return
    if settings.auth.auth_mode != "supabase":
        raise RuntimeError("Production requires AUTH_MODE=supabase")
    if not _is_postgres_url(settings.db.database_url):
        raise RuntimeError("Production requires a PostgreSQL DATABASE_URL")
    if settings.db.auto_create_tables:
        raise RuntimeError("Production requires AUTO_CREATE_TABLES=false")
    if settings.docs_enabled:
        raise RuntimeError("Production requires DOCS_ENABLED=false")
    if not settings.source_require_https:
        raise RuntimeError("Production requires SOURCE_REQUIRE_HTTPS=true")
    if not settings.cors_allowed_origins:
        raise RuntimeError("Production requires at least one CORS_ALLOWED_ORIGINS value")
    if any(_is_invalid_production_origin(origin) for origin in settings.cors_allowed_origins):
        raise RuntimeError(
            "Production CORS_ALLOWED_ORIGINS must be HTTPS origins, except explicit localhost "
            "HTTP origins for development"
        )
    if not settings.trusted_hosts:
        raise RuntimeError("Production requires at least one TRUSTED_HOSTS value")
    if any(_is_invalid_production_host(host) for host in settings.trusted_hosts):
        raise RuntimeError("Production TRUSTED_HOSTS must be explicit non-local hosts")
    if not settings.auth.supabase_project_url:
        raise RuntimeError("Production requires SUPABASE_PROJECT_URL")
    if not settings.auth.supabase_service_role_key:
        # The API deletes Supabase logins on account deletion; the worker stores thumbnails.
        raise RuntimeError("Production requires SUPABASE_SERVICE_ROLE_KEY")
    if not settings.auth.supabase_jwt_audience:
        raise RuntimeError("Production requires SUPABASE_JWT_AUDIENCE")


@lru_cache
def get_settings() -> Settings:
    load_dotenv(BASE_DIR / ".env")
    settings = Settings()
    validate_settings(settings)
    return settings
