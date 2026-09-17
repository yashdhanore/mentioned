from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from src.jobs.models import Job, JobStatus

EXPO_PUSH_SEND_URL = "https://exp.host/--/api/v2/push/send"
JOB_STATUS_NOTIFICATION_CHANNEL_ID = "job-status"
DEVICE_NOT_REGISTERED = "DeviceNotRegistered"

logger = logging.getLogger(__name__)


class PushDeliveryRetryableError(Exception):
    """Raised when a push request can be retried later."""


@dataclass(frozen=True)
class PushDeliveryResult:
    disabled_tokens: set[str]


def _notification_body(job: Job) -> str:
    if job.status == JobStatus.FAILED:
        return "We couldn't process your Reel."
    return "Your Reel has been processed."


def _message_for_token(job: Job, expo_push_token: str) -> dict[str, object]:
    return {
        "to": expo_push_token,
        "title": "Mentioned",
        "body": _notification_body(job),
        "data": {"job_id": str(job.id)},
        "channelId": JOB_STATUS_NOTIFICATION_CHANNEL_ID,
    }


def _response_items(payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        raise PushDeliveryRetryableError("Expo push response was not a JSON object")

    errors = payload.get("errors")
    if errors:
        raise PushDeliveryRetryableError(f"Expo push request failed: {errors}")

    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def send_job_push_notifications(job: Job, expo_push_tokens: list[str]) -> PushDeliveryResult:
    if not expo_push_tokens:
        return PushDeliveryResult(disabled_tokens=set())

    messages = [_message_for_token(job, token) for token in expo_push_tokens]
    try:
        response = httpx.post(EXPO_PUSH_SEND_URL, json=messages, timeout=10)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise PushDeliveryRetryableError(str(exc)) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise PushDeliveryRetryableError("Expo push response was not valid JSON") from exc

    items = _response_items(payload)
    disabled_tokens: set[str] = set()
    for token, item in zip(expo_push_tokens, items, strict=False):
        if item.get("status") != "error":
            continue
        details = item.get("details")
        error = details.get("error") if isinstance(details, dict) else None
        if error == DEVICE_NOT_REGISTERED:
            disabled_tokens.add(token)
        else:
            logger.warning("Expo push ticket error for token %s: %s", token, item)

    return PushDeliveryResult(disabled_tokens=disabled_tokens)
