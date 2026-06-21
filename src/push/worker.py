from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.engine import Engine
from sqlmodel import Session

from src.jobs.models import Job, JobStatus
from src.jobs.service import get_job
from src.push.expo import (
    PushDeliveryResult,
    PushDeliveryRetryableError,
    send_job_push_notifications,
)
from src.push.queue import PushNotificationMessage, archive_push_notification_message
from src.push.service import disable_push_token_value, list_active_push_tokens


logger = logging.getLogger(__name__)

PushSender = Callable[[Job, list[str]], PushDeliveryResult]


def process_push_notification_message(
    message: PushNotificationMessage,
    worker_engine: Engine,
    send_notifications: PushSender = send_job_push_notifications,
) -> None:
    with Session(worker_engine) as session:
        job = get_job(session, message.job_id)
        if not job:
            logger.warning(
                "Archiving push message %s for missing job %s",
                message.msg_id,
                message.job_id,
            )
            archive_push_notification_message(session, message.msg_id)
            session.commit()
            return
        if job.status == JobStatus.PENDING:
            logger.info(
                "Leaving push message %s unarchived for pending job %s",
                message.msg_id,
                job.id,
            )
            return
        tokens = list_active_push_tokens(session, job.owner_id)

    try:
        result = send_notifications(job, tokens)
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
        logger.info("Archived push message %s for job %s", message.msg_id, job.id)
