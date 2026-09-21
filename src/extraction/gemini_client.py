from __future__ import annotations

from google import genai
from google.genai.types import HttpOptions, HttpRetryOptions

from src.config import Settings


def get_gemini_client(settings: Settings) -> genai.Client:
    retry_options = HttpRetryOptions(attempts=1)
    timeout_ms = settings.gemini.gemini_timeout_seconds * 1000
    if settings.gemini.use_vertexai:
        if not settings.gemini.vertex_project:
            raise RuntimeError("GOOGLE_CLOUD_PROJECT is not configured for Vertex AI")
        return genai.Client(
            vertexai=True,
            project=settings.gemini.vertex_project,
            location=settings.gemini.vertex_location,
            http_options=HttpOptions(
                api_version="v1", retry_options=retry_options, timeout=timeout_ms
            ),
        )

    api_key = settings.gemini.gemini_api_key
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    return genai.Client(
        api_key=api_key,
        http_options=HttpOptions(retry_options=retry_options, timeout=timeout_ms),
    )
