from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
SUPPORTED_AUTH_MODES = {"dev", "supabase"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "Mentioned Backend"
    app_env: str = "local"
    database_url: str = "sqlite:///app.db"
    worker_database_url: str | None = None
    data_dir: Path = Path("data")
    auto_create_tables: bool = True
    docs_enabled: bool = True
    cors_allowed_origins: tuple[str, ...] = ()
    trusted_hosts: tuple[str, ...] = ()
    worker_poll_interval_seconds: float = 2.0
    worker_stale_timeout_seconds: int = 15 * 60
    worker_retry_base_delay_seconds: int = 30
    worker_id: str = "worker-local"
    auth_mode: str = "dev"
    dev_user_id: str = "00000000-0000-4000-8000-000000000001"
    supabase_project_url: str | None = None
    supabase_jwt_secret: str | None = None
    supabase_jwt_audience: str = "authenticated"
    source_require_https: bool = False
    max_job_create_burst_per_minute: int = 3
    max_jobs_created_per_day: int = 25
    max_active_jobs_per_user: int = 5
    asr_provider: str = "none"
    ocr_provider: str = "none"
    multimodal_llm_provider: str = "none"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_asr_model: str = "gpt-4o-mini-transcribe"
    openai_asr_prompt: str | None = None
    max_asr_audio_bytes: int = 25 * 1024 * 1024
    openai_multimodal_model: str = "gpt-5.4-nano"
    openai_reasoning_effort: str = "low"
    openai_text_verbosity: str = "low"
    openai_store_responses: bool = False
    max_selected_frames: int = 8
    max_selected_post_images: int = 10
    max_llm_images: int = 20
    max_llm_crops: int = 12
    max_llm_calls_per_job: int = 1
    max_image_long_edge_px: int = 1280
    llm_timeout_seconds: float = 60.0

    @property
    def artifact_dir(self) -> Path:
        return self.data_dir / "artifacts"

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


def validate_settings(settings: Settings) -> None:
    if settings.auth_mode not in SUPPORTED_AUTH_MODES:
        raise RuntimeError(f"Unsupported AUTH_MODE: {settings.auth_mode}")
    if settings.is_production and settings.auth_mode != "supabase":
        raise RuntimeError("Production requires AUTH_MODE=supabase")


@lru_cache
def get_settings() -> Settings:
    load_dotenv(BASE_DIR / ".env")
    database_url = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}")
    app_env = os.getenv("APP_ENV", "local").strip().casefold()
    data_dir = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
    auto_create_default = database_url.startswith("sqlite") and app_env != "production"
    settings = Settings(
        app_name="Mentioned Backend",
        app_env=app_env,
        database_url=database_url,
        worker_database_url=_env_optional("WORKER_DATABASE_URL"),
        data_dir=data_dir,
        auto_create_tables=_env_bool("AUTO_CREATE_TABLES", auto_create_default),
        docs_enabled=_env_bool("DOCS_ENABLED", app_env != "production"),
        cors_allowed_origins=_env_csv("CORS_ALLOWED_ORIGINS"),
        trusted_hosts=_env_csv("TRUSTED_HOSTS"),
        worker_poll_interval_seconds=_env_float("WORKER_POLL_INTERVAL_SECONDS", 2.0),
        worker_stale_timeout_seconds=_env_int("WORKER_STALE_TIMEOUT_SECONDS", 15 * 60),
        worker_retry_base_delay_seconds=_env_int("WORKER_RETRY_BASE_DELAY_SECONDS", 30),
        worker_id=os.getenv("WORKER_ID", "worker-local").strip(),
        auth_mode=os.getenv("AUTH_MODE", "dev").strip().casefold(),
        dev_user_id=os.getenv("DEV_USER_ID", "00000000-0000-4000-8000-000000000001").strip(),
        supabase_project_url=_env_optional("SUPABASE_PROJECT_URL"),
        supabase_jwt_secret=_env_optional("SUPABASE_JWT_SECRET"),
        supabase_jwt_audience=os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated").strip(),
        source_require_https=_env_bool("SOURCE_REQUIRE_HTTPS", app_env == "production"),
        max_job_create_burst_per_minute=_env_int("MAX_JOB_CREATE_BURST_PER_MINUTE", 3),
        max_jobs_created_per_day=_env_int("MAX_JOBS_CREATED_PER_DAY", 25),
        max_active_jobs_per_user=_env_int("MAX_ACTIVE_JOBS_PER_USER", 5),
        asr_provider=os.getenv("ASR_PROVIDER", "none").strip().casefold(),
        ocr_provider=os.getenv("OCR_PROVIDER", "none").strip().casefold(),
        multimodal_llm_provider=os.getenv("MULTIMODAL_LLM_PROVIDER", "none").strip().casefold(),
        openai_api_key=_env_optional("OPENAI_API_KEY"),
        openai_base_url=_env_optional("OPENAI_BASE_URL"),
        openai_asr_model=os.getenv("OPENAI_ASR_MODEL", "gpt-4o-mini-transcribe").strip(),
        openai_asr_prompt=_env_optional("OPENAI_ASR_PROMPT"),
        max_asr_audio_bytes=_env_int("MAX_ASR_AUDIO_BYTES", 25 * 1024 * 1024),
        openai_multimodal_model=os.getenv("OPENAI_MULTIMODAL_MODEL", "gpt-5.4-nano").strip(),
        openai_reasoning_effort=os.getenv("OPENAI_REASONING_EFFORT", "low").strip(),
        openai_text_verbosity=os.getenv("OPENAI_TEXT_VERBOSITY", "low").strip(),
        openai_store_responses=_env_bool("OPENAI_STORE_RESPONSES", False),
        max_selected_frames=_env_int("MAX_SELECTED_FRAMES", 8),
        max_selected_post_images=_env_int("MAX_SELECTED_POST_IMAGES", 10),
        max_llm_images=_env_int("MAX_LLM_IMAGES", 20),
        max_llm_crops=_env_int("MAX_LLM_CROPS", 12),
        max_llm_calls_per_job=_env_int("MAX_LLM_CALLS_PER_JOB", 1),
        max_image_long_edge_px=_env_int("MAX_IMAGE_LONG_EDGE_PX", 1280),
        llm_timeout_seconds=_env_float("LLM_TIMEOUT_SECONDS", 60.0),
    )
    validate_settings(settings)
    settings.artifact_dir.mkdir(parents=True, exist_ok=True)
    return settings
