"""Langfuse tracing for the worker's extraction pipeline and the eval scripts.

Every Langfuse call in the app goes through the client this module configures. Tracing is on
only when both `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set, so tests, local dev,
and a deploy without the keys run unchanged and export nothing. The SDK exports on a
background thread and swallows its own errors, so a Langfuse outage never fails a Reel.

What a trace may carry is deliberately narrow: prompts, captions, model replies, token
counts, and cost, but never media bytes (only their name, type, and size) and never a user
id, because a source is a cache shared by everyone who saved the Reel.

The SDK's own `get_client()` is not used: it returns a disabled client as soon as a second
Langfuse client exists in the process.
"""

from __future__ import annotations

import logging
import mimetypes
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx
from langfuse import Langfuse

from src.config import Settings, get_settings
from src.extraction.pricing import gemini_cost_details, gemini_usage_details

logger = logging.getLogger(__name__)

# Placeholder credentials for the disabled client, so the SDK does not warn about missing
# keys on every start in tests and local dev.
_DISABLED_KEY = "tracing-disabled"

_client: Langfuse | None = None
_lock = threading.Lock()


def configure_tracing(
    settings: Settings, *, environment: str | None = None, **client_options: Any
) -> Langfuse:
    """Build the process's Langfuse client from settings and make it the one `langfuse()`
    returns. Traces are filed under `environment`, `APP_ENV` by default, so eval runs and
    local dev never mix with production. `client_options` pass through to `Langfuse(...)`."""
    global _client
    config = settings.langfuse
    environment = environment or settings.app_env
    with _lock:
        if config.enabled:
            client = Langfuse(
                public_key=config.public_key,
                secret_key=config.secret_key,
                base_url=config.base_url,
                environment=environment,
                **client_options,
            )
            logger.info("Langfuse tracing enabled (%s, env=%s)", config.base_url, environment)
        else:
            client = Langfuse(
                public_key=_DISABLED_KEY, secret_key=_DISABLED_KEY, tracing_enabled=False
            )
            logger.info("Langfuse tracing disabled: LANGFUSE_PUBLIC_KEY/SECRET_KEY not set")
        _client = client
    return client


def langfuse() -> Langfuse:
    """The configured client, configured from `get_settings()` on first use."""
    client = _client
    if client is None:
        return configure_tracing(get_settings())
    return client


def shutdown_tracing() -> None:
    """Send everything still queued, then stop the export threads.

    The SDK keeps one client per public key for the life of the process, so configuring the
    same key again after this returns the stopped client; a process shuts down once, at exit."""
    global _client
    with _lock:
        client, _client = _client, None
    if client is not None:
        client.shutdown()


def flush_tracing() -> None:
    if _client is not None:
        _client.flush()


def describe_error(exc: BaseException) -> str:
    """A status message for a failed step. httpx errors keep only their type: their message
    carries the request URL, which for Google Books includes the API key."""
    if isinstance(exc, httpx.HTTPError):
        return type(exc).__name__
    return f"{type(exc).__name__}: {exc}"


@contextmanager
def observe_step(name: str, *, as_type: str = "span", **fields: Any) -> Iterator[Any]:
    """`start_as_current_observation` that also marks the observation ERROR, with a safe
    message, when the block raises."""
    with langfuse().start_as_current_observation(name=name, as_type=as_type, **fields) as step:
        try:
            yield step
        except Exception as exc:
            step.update(level="ERROR", status_message=describe_error(exc))
            raise


def media_view(path: Path) -> dict[str, Any]:
    """What a trace records about a media file instead of its bytes."""
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return {"file": path.name, "mime_type": mime_type, "bytes": path.stat().st_size}


def media_placeholder(description: str) -> dict[str, str]:
    """A text part standing in for media the model saw but the trace leaves out."""
    return {"type": "text", "text": f"[{description}; not captured in the trace]"}


def user_message(*parts: dict[str, str]) -> list[dict[str, Any]]:
    """A one-message conversation, the input shape Langfuse renders as a chat."""
    return [{"role": "user", "content": list(parts)}]


def text_part(text: str) -> dict[str, str]:
    return {"type": "text", "text": text}


_USAGE_FIELDS = (
    "prompt_token_count",
    "prompt_tokens_details",
    "candidates_token_count",
    "thoughts_token_count",
    "total_token_count",
)


def gemini_usage(response: Any) -> dict[str, Any] | None:
    """A response's `usage_metadata` as a plain dict, the shape `pricing.py` reads."""
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        return usage.model_dump(mode="json", exclude_none=True)
    return {name: getattr(usage, name) for name in _USAGE_FIELDS if getattr(usage, name, None)}


def record_gemini_reply(generation: Any, *, model: str, response: Any) -> None:
    """Put a `generate_content` response's token usage, cost, and finish state on a
    generation. Cost comes from `src/extraction/pricing.py`, the table the evals use; a model
    it does not price is left to Langfuse's own model prices. Never raises: a response shape
    this does not expect must not fail the extraction it describes."""
    try:
        usage_details = gemini_usage_details(gemini_usage(response))
        fields: dict[str, Any] = {"metadata": gemini_finish_state(response)}
        if usage_details is not None:
            fields["usage_details"] = usage_details
            cost_details = gemini_cost_details(model, usage_details)
            if cost_details is not None:
                # Langfuse derives a usage total but not a cost total; without one its cost
                # views read zero.
                fields["cost_details"] = {**cost_details, "total": sum(cost_details.values())}
        generation.update(**fields)
    except Exception:
        logger.warning("Could not record Gemini usage on the trace", exc_info=True)


def gemini_finish_state(response: Any) -> dict[str, str | None]:
    feedback = getattr(response, "prompt_feedback", None)
    block_reason = getattr(feedback, "block_reason", None)
    candidates = getattr(response, "candidates", None) or []
    finish_reason = getattr(candidates[0], "finish_reason", None) if candidates else None
    return {
        "finish_reason": _enum_name(finish_reason),
        "block_reason": _enum_name(block_reason),
    }


def _enum_name(value: Any) -> str | None:
    if value is None:
        return None
    return getattr(value, "name", None) or str(value)
