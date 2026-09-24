"""Gemini token prices, shared by production tracing and the eval scripts.

One table, so the cost a Langfuse trace shows for a production extraction is computed the
same way as the cost per correct mention in `evals/README.md`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

PRICING_SOURCE = "Gemini Developer API paid tier, standard mode, checked 2026-09-22"

# USD per 1M tokens. Gemini pricing separates audio input from text/image/video input.
PRICE_TABLE: dict[str, dict[str, float]] = {
    "gemini-2.5-flash": {
        "input_text_image_video": 0.30,
        "input_audio": 1.00,
        "output": 2.50,
    },
    "gemini-3.1-flash-lite": {
        "input_text_image_video": 0.25,
        "input_audio": 0.50,
        "output": 1.50,
    },
    "gemini-3.5-flash-lite": {
        "input_text_image_video": 0.30,
        "input_audio": 0.30,
        "output": 2.50,
    },
    "gemini-3.5-flash": {
        "input_text_image_video": 1.50,
        "input_audio": 1.50,
        "output": 9.00,
    },
    # Launch pricing through 2026-12-31; doubles to 1.50 input / 7.50 output after.
    "gemini-3.8-flash": {
        "input_text_image_video": 0.75,
        "input_audio": 0.75,
        "output": 3.75,
    },
}


def _int_value(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _modality_name(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    name = getattr(value, "name", None)
    if isinstance(name, str):
        return name.upper()
    return str(value).split(".")[-1].upper()


def prompt_tokens_by_modality(details: Any) -> dict[str, int]:
    totals: dict[str, int] = {}
    if not isinstance(details, list):
        return totals
    for item in details:
        if not isinstance(item, Mapping):
            continue
        modality = _modality_name(item.get("modality"))
        token_count = _int_value(item.get("token_count"))
        if token_count:
            totals[modality] = totals.get(modality, 0) + token_count
    return totals


def gemini_usage_details(usage: Mapping[str, Any] | None) -> dict[str, int] | None:
    """Split Gemini `usage_metadata` (as `model_dump(mode="json")`) into the non-overlapping
    buckets Gemini bills separately: text/image/video input, audio input, the answer, and
    thinking. Thinking is billed at the output rate."""
    if not usage:
        return None
    prompt_tokens = _int_value(usage.get("prompt_token_count"))
    audio_tokens = prompt_tokens_by_modality(usage.get("prompt_tokens_details")).get("AUDIO", 0)
    return {
        "input": max(prompt_tokens - audio_tokens, 0),
        "input_audio": audio_tokens,
        "output": _int_value(usage.get("candidates_token_count")),
        "output_reasoning": _int_value(usage.get("thoughts_token_count")),
    }


def gemini_cost_details(
    model: str, usage_details: Mapping[str, int] | None
) -> dict[str, float] | None:
    """USD per bucket of `gemini_usage_details`, or None for a model the table does not price."""
    rates = PRICE_TABLE.get(model)
    if not rates or usage_details is None:
        return None
    return {
        "input": usage_details["input"] * rates["input_text_image_video"] / 1_000_000,
        "input_audio": usage_details["input_audio"] * rates["input_audio"] / 1_000_000,
        "output": usage_details["output"] * rates["output"] / 1_000_000,
        "output_reasoning": usage_details["output_reasoning"] * rates["output"] / 1_000_000,
    }
