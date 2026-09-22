from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

import httpx

from src.push.service import SourcePushTarget
from src.sources.models import Source, SourceStatus

EXPO_PUSH_SEND_URL = "https://exp.host/--/api/v2/push/send"
EXPO_PUSH_TIMEOUT_SECONDS = 10
# The mobile app still names its Android notification channel "job-status".
SOURCE_STATUS_NOTIFICATION_CHANNEL_ID = "job-status"
DEVICE_NOT_REGISTERED = "DeviceNotRegistered"

logger = logging.getLogger(__name__)


class PushDeliveryRetryableError(Exception):
    """Raised when a push request can be retried later."""


@dataclass(frozen=True)
class PushDeliveryResult:
    disabled_tokens: set[str]


def _notification_body(source: Source) -> str:
    if source.status == SourceStatus.FAILED:
        return "We couldn't process your Reel."
    return "Your Reel has been processed."


def _message_for_token(
    saved_source_id: UUID, source: Source, expo_push_token: str
) -> dict[str, object]:
    return {
        "to": expo_push_token,
        "title": "Mentioned",
        "body": _notification_body(source),
        "data": {"saved_source_id": str(saved_source_id)},
        "channelId": SOURCE_STATUS_NOTIFICATION_CHANNEL_ID,
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


def send_source_push_notifications(
    source: Source, targets: list[SourcePushTarget]
) -> PushDeliveryResult:
    messages: list[dict[str, object]] = []
    tokens_in_order: list[str] = []
    for target in targets:
        for expo_push_token in target.expo_push_tokens:
            messages.append(_message_for_token(target.saved_source_id, source, expo_push_token))
            tokens_in_order.append(expo_push_token)

    if not messages:
        return PushDeliveryResult(disabled_tokens=set())

    try:
        response = httpx.post(EXPO_PUSH_SEND_URL, json=messages, timeout=EXPO_PUSH_TIMEOUT_SECONDS)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise PushDeliveryRetryableError(str(exc)) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise PushDeliveryRetryableError("Expo push response was not valid JSON") from exc

    items = _response_items(payload)
    disabled_tokens: set[str] = set()
    for token, item in zip(tokens_in_order, items, strict=False):
        if item.get("status") != "error":
            continue
        details = item.get("details")
        error = details.get("error") if isinstance(details, dict) else None
        if error == DEVICE_NOT_REGISTERED:
            disabled_tokens.add(token)
        else:
            # Log the error code, not the ticket: the ticket and its message carry the push
            # token, which is enough to send notifications to that device.
            logger.warning("Expo push ticket error: %s", error or "unknown")

    return PushDeliveryResult(disabled_tokens=disabled_tokens)
