from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.config import Settings


@dataclass(slots=True)
class AudioTranscriptionResult:
    text: str
    provider: str
    model: str
    response: dict[str, Any]


def _response_to_dict(response: Any) -> dict[str, Any]:
    if hasattr(response, "model_dump"):
        return response.model_dump(mode="json")
    if isinstance(response, dict):
        return response
    text = getattr(response, "text", None)
    return {"text": text} if isinstance(text, str) else {}


def transcribe_audio_with_openai(audio_path: Path, settings: Settings) -> AudioTranscriptionResult:
    if settings.openai_api_key is None:
        raise ValueError("OPENAI_API_KEY is required when ASR_PROVIDER=openai")
    audio_size = audio_path.stat().st_size
    if audio_size > settings.max_asr_audio_bytes:
        raise ValueError(
            f"Audio file is {audio_size} bytes, exceeding MAX_ASR_AUDIO_BYTES={settings.max_asr_audio_bytes}"
        )

    client_kwargs: dict[str, Any] = {
        "api_key": settings.openai_api_key,
        "timeout": settings.llm_timeout_seconds,
    }
    if settings.openai_base_url is not None:
        client_kwargs["base_url"] = settings.openai_base_url
    client = OpenAI(**client_kwargs)

    request: dict[str, Any] = {
        "model": settings.openai_asr_model,
        "response_format": "json",
    }
    if settings.openai_asr_prompt is not None:
        request["prompt"] = settings.openai_asr_prompt

    with audio_path.open("rb") as audio_file:
        response = client.audio.transcriptions.create(file=audio_file, **request)

    response_dict = _response_to_dict(response)
    text = response_dict.get("text") or getattr(response, "text", None)
    if not isinstance(text, str):
        raise ValueError("OpenAI transcription response did not include text")
    return AudioTranscriptionResult(
        text=text.strip(),
        provider="openai",
        model=settings.openai_asr_model,
        response=response_dict,
    )
