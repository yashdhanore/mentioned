from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.engine import Engine
from sqlmodel import Session

from src.push.expo import (
    PushDeliveryResult,
    PushDeliveryRetryableError,
    send_source_push_notifications,
)
from src.push.queue import PushNotificationMessage, archive_push_notification_message
from src.push.service import (
    SourcePushTarget,
    disable_push_token_value,
    list_push_targets_for_source,
)
from src.sources.models import Source, SourceStatus

logger = logging.getLogger(__name__)

PushSender = Callable[[Source, list[SourcePushTarget]], PushDeliveryResult]


def process_push_notification_message(
    message: PushNotificationMessage,
    worker_engine: Engine,
    send_notifications: PushSender = send_source_push_notifications,
) -> None:
    with Session(worker_engine) as session:
        source = session.get(Source, message.source_id)
        if not source:
            logger.warning(
                "Archiving push message %s for missing source %s",
                message.msg_id,
                message.source_id,
            )
            archive_push_notification_message(session, message.msg_id)
            session.commit()
            return
        if source.status not in (SourceStatus.DONE, SourceStatus.FAILED):
            logger.info(
                "Leaving push message %s unarchived for unfinished source %s",
                message.msg_id,
                source.id,
            )
            return
        targets = list_push_targets_for_source(session, source.id)

    try:
        result = send_notifications(source, targets)
    except PushDeliveryRetryableError as exc:
        logger.warning(
            "Leaving push message %s unarchived after retryable delivery failure: %s",
            message.msg_id,
            exc,
        )
        return

    with Session(worker_engine) as session:
        for expo_push_token in result.disabled_tokens:
            disable_push_token_value(session, expo_push_token)
        archive_push_notification_message(session, message.msg_id)
        session.commit()
        logger.info("Archived push message %s for source %s", message.msg_id, source.id)
