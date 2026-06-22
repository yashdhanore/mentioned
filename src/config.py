from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
SUPPORTED_AUTH_MODES = {"dev", "supabase"}
HARD_MAX_MEDIA_DURATION_SECONDS = 300
HARD_MAX_MEDIA_FILE_BYTES = 100 * 1024 * 1024
HARD_MAX_MEDIA_TOTAL_BYTES = 150 * 1024 * 1024
HARD_MAX_MEDIA_VIDEO_COUNT = 3
HARD_MAX_GEMINI_TOTAL_ATTEMPTS = 3


@dataclass(frozen=True)
class DBConfig:
    database_url: str = "sqlite:///app.db"
    worker_database_url: str | None = None
    auto_create_tables: bool = True


@dataclass(frozen=True)
class AuthConfig:
    auth_mode: str = "dev"
    dev_user_id: str = "00000000-0000-4000-8000-000000000001"
    supabase_project_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_jwt_secret: str | None = None
    supabase_jwt_audience: str = "authenticated"


@dataclass(frozen=True)
class GeminiConfig:
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_total_attempts: int = 3
    use_vertexai: bool = False
    vertex_project: str | None = None
    vertex_location: str = "global"


@dataclass(frozen=True)
class GoogleBooksConfig:
    api_key: str | None = None


@dataclass(frozen=True)
class Settings:
    app_name: str = "Mentioned Backend"
    app_env: str = "local"
    docs_enabled: bool = True
    cors_allowed_origins: tuple[str, ...] = ()
    trusted_hosts: tuple[str, ...] = ()
    source_require_https: bool = False
    extraction_backend: str = "gemini"

    # Worker
    worker_poll_interval_seconds: float = 2.0
    worker_stale_timeout_seconds: int = 15 * 60
    worker_queue_visibility_timeout_seconds: int = 30 * 60
    worker_queue_max_poll_seconds: int = 5
    worker_queue_poll_interval_ms: int = 100
    worker_id: str = "worker-local"

    # Media download limits
    media_download_timeout_seconds: int = 120
    media_download_format: str | None = None
    max_media_file_bytes: int = 50 * 1024 * 1024
    max_media_total_bytes: int = 100 * 1024 * 1024
    max_media_duration_seconds: int = 180
    max_media_video_count: int = 1
    media_transcode_video_bitrate: str = "1100k"
    media_transcode_audio_bitrate: str = "96k"

    # Rate limits
    max_job_create_burst_per_minute: int = 3
    max_jobs_created_per_day: int = 25
    max_active_jobs_per_user: int = 5

    # Sub-configs
    db: DBConfig = DBConfig()
    auth: AuthConfig = AuthConfig()
    gemini: GeminiConfig = GeminiConfig()
    google_books: GoogleBooksConfig = GoogleBooksConfig()

    @property
    def database_url(self) -> str:
        return self.db.database_url

    @property
    def worker_database_url(self) -> str | None:
        return self.db.worker_database_url

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return float(value)


def _env_optional(name: str) -> str | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def _env_csv(name: str) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None or not value.strip():
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _is_postgres_url(database_url: str) -> bool:
    return database_url.startswith("postgresql://") or database_url.startswith("postgresql+")


def _is_local_hostname(hostname: str | None) -> bool:
    return hostname is not None and hostname.casefold() in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


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
    if not 1 <= settings.max_media_duration_seconds <= HARD_MAX_MEDIA_DURATION_SECONDS:
        raise RuntimeError(
            f"MAX_MEDIA_DURATION_SECONDS must be between 1 and {HARD_MAX_MEDIA_DURATION_SECONDS}"
        )
    if not 1 <= settings.max_media_file_bytes <= HARD_MAX_MEDIA_FILE_BYTES:
        raise RuntimeError(f"MAX_MEDIA_FILE_BYTES must be between 1 and {HARD_MAX_MEDIA_FILE_BYTES}")
    if not 1 <= settings.max_media_total_bytes <= HARD_MAX_MEDIA_TOTAL_BYTES:
        raise RuntimeError(f"MAX_MEDIA_TOTAL_BYTES must be between 1 and {HARD_MAX_MEDIA_TOTAL_BYTES}")
    if settings.max_media_file_bytes > settings.max_media_total_bytes:
        raise RuntimeError("MAX_MEDIA_FILE_BYTES must be less than or equal to MAX_MEDIA_TOTAL_BYTES")
    if not 1 <= settings.max_media_video_count <= HARD_MAX_MEDIA_VIDEO_COUNT:
        raise RuntimeError(f"MAX_MEDIA_VIDEO_COUNT must be between 1 and {HARD_MAX_MEDIA_VIDEO_COUNT}")
    if not 1 <= settings.gemini.gemini_total_attempts <= HARD_MAX_GEMINI_TOTAL_ATTEMPTS:
        raise RuntimeError(
            f"GEMINI_TOTAL_ATTEMPTS must be between 1 and {HARD_MAX_GEMINI_TOTAL_ATTEMPTS}"
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
            "Production CORS_ALLOWED_ORIGINS must be HTTPS origins, except explicit localhost HTTP origins for development"
        )
    if not settings.trusted_hosts:
        raise RuntimeError("Production requires at least one TRUSTED_HOSTS value")
    if any(_is_invalid_production_host(host) for host in settings.trusted_hosts):
        raise RuntimeError("Production TRUSTED_HOSTS must be explicit non-local hosts")
    if not settings.auth.supabase_project_url:
        raise RuntimeError("Production requires SUPABASE_PROJECT_URL")
    if not settings.auth.supabase_jwt_audience:
        raise RuntimeError("Production requires SUPABASE_JWT_AUDIENCE")


@lru_cache
def get_settings() -> Settings:
    load_dotenv(BASE_DIR / ".env")
    database_url = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}")
    app_env = os.getenv("APP_ENV", "local").strip().casefold()
    auto_create_default = database_url.startswith("sqlite") and app_env != "production"
    settings = Settings(
        app_name="Mentioned Backend",
        app_env=app_env,
        docs_enabled=_env_bool("DOCS_ENABLED", app_env != "production"),
        cors_allowed_origins=_env_csv("CORS_ALLOWED_ORIGINS"),
        trusted_hosts=_env_csv("TRUSTED_HOSTS"),
        source_require_https=_env_bool("SOURCE_REQUIRE_HTTPS", app_env == "production"),
        worker_poll_interval_seconds=_env_float("WORKER_POLL_INTERVAL_SECONDS", 2.0),
        worker_stale_timeout_seconds=_env_int("WORKER_STALE_TIMEOUT_SECONDS", 15 * 60),
        worker_queue_visibility_timeout_seconds=_env_int(
            "WORKER_QUEUE_VISIBILITY_TIMEOUT_SECONDS", 30 * 60
        ),
        worker_queue_max_poll_seconds=_env_int("WORKER_QUEUE_MAX_POLL_SECONDS", 5),
        worker_queue_poll_interval_ms=_env_int("WORKER_QUEUE_POLL_INTERVAL_MS", 100),
        worker_id=os.getenv("WORKER_ID", "worker-local").strip(),
        media_download_timeout_seconds=_env_int("MEDIA_DOWNLOAD_TIMEOUT_SECONDS", 120),
        media_download_format=_env_optional("MEDIA_DOWNLOAD_FORMAT"),
        max_media_file_bytes=_env_int("MAX_MEDIA_FILE_BYTES", 50 * 1024 * 1024),
        max_media_total_bytes=_env_int("MAX_MEDIA_TOTAL_BYTES", 100 * 1024 * 1024),
        max_media_duration_seconds=_env_int("MAX_MEDIA_DURATION_SECONDS", 180),
        max_media_video_count=_env_int("MAX_MEDIA_VIDEO_COUNT", 1),
        media_transcode_video_bitrate=os.getenv("MEDIA_TRANSCODE_VIDEO_BITRATE", "1100k").strip(),
        media_transcode_audio_bitrate=os.getenv("MEDIA_TRANSCODE_AUDIO_BITRATE", "96k").strip(),
        max_job_create_burst_per_minute=_env_int("MAX_JOB_CREATE_BURST_PER_MINUTE", 3),
        max_jobs_created_per_day=_env_int("MAX_JOBS_CREATED_PER_DAY", 25),
        max_active_jobs_per_user=_env_int("MAX_ACTIVE_JOBS_PER_USER", 5),
        db=DBConfig(
            database_url=database_url,
            worker_database_url=_env_optional("WORKER_DATABASE_URL"),
            auto_create_tables=_env_bool("AUTO_CREATE_TABLES", auto_create_default),
        ),
        auth=AuthConfig(
            auth_mode=os.getenv("AUTH_MODE", "dev").strip().casefold(),
            dev_user_id=os.getenv("DEV_USER_ID", "00000000-0000-4000-8000-000000000001").strip(),
            supabase_project_url=_env_optional("SUPABASE_PROJECT_URL"),
            supabase_service_role_key=_env_optional("SUPABASE_SERVICE_ROLE_KEY"),
            supabase_jwt_secret=_env_optional("SUPABASE_JWT_SECRET"),
            supabase_jwt_audience=os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated").strip(),
        ),
        gemini=GeminiConfig(
            gemini_api_key=_env_optional("GEMINI_API_KEY"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip(),
            gemini_total_attempts=_env_int("GEMINI_TOTAL_ATTEMPTS", 3),
            use_vertexai=_env_bool(
                "GEMINI_USE_VERTEXAI",
                _env_bool("GOOGLE_GENAI_USE_VERTEXAI", False),
            ),
            vertex_project=_env_optional("GEMINI_VERTEX_PROJECT") or _env_optional("GOOGLE_CLOUD_PROJECT"),
            vertex_location=(
                os.getenv("GEMINI_VERTEX_LOCATION")
                or os.getenv("GOOGLE_CLOUD_LOCATION")
                or "global"
            ).strip(),
        ),
        google_books=GoogleBooksConfig(
            api_key=_env_optional("GOOGLE_BOOKS_API_KEY"),
        ),
    )
    validate_settings(settings)
    return settings
