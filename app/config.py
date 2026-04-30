from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    app_name: str
    database_url: str
    data_dir: Path
    worker_poll_interval_seconds: float
    asr_provider: str
    ocr_provider: str
    multimodal_llm_provider: str
    openai_api_key: str | None
    openai_base_url: str | None
    openai_asr_model: str
    openai_asr_prompt: str | None
    max_asr_audio_bytes: int
    openai_multimodal_model: str
    openai_reasoning_effort: str
    openai_text_verbosity: str
    openai_store_responses: bool
    max_selected_frames: int
    max_selected_post_images: int
    max_llm_images: int
    max_llm_crops: int
    max_llm_calls_per_job: int
    max_image_long_edge_px: int
    llm_timeout_seconds: float

    @property
    def artifact_dir(self) -> Path:
        return self.data_dir / "artifacts"


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
    return value


@lru_cache
def get_settings() -> Settings:
    load_dotenv(BASE_DIR / ".env")
    data_dir = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
    settings = Settings(
        app_name="Mentioned Backend",
        database_url=os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}"),
        data_dir=data_dir,
        worker_poll_interval_seconds=float(
            os.getenv("WORKER_POLL_INTERVAL_SECONDS", "2")
        ),
        asr_provider=os.getenv("ASR_PROVIDER", "none").strip().casefold(),
        ocr_provider=os.getenv("OCR_PROVIDER", "tesseract").strip().casefold(),
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
    settings.artifact_dir.mkdir(parents=True, exist_ok=True)
    return settings
