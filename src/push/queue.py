from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlmodel import Session

from src.ids import parse_uuid
from src.pgmq import is_postgres_session, parse_message_payload

logger = logging.getLogger(__name__)

PUSH_NOTIFICATIONS_QUEUE = "push_notifications"


@dataclass(frozen=True)
class PushNotificationMessage:
    msg_id: int
    source_id: UUID
    read_count: int


def enqueue_push_notification(session: Session, source_id: str | UUID) -> None:
    if not is_postgres_session(session):
        return

    message = json.dumps({"v": 1, "source_id": str(source_id)})
    session.execute(
        text(
            """
            select * from pgmq.send(
              :queue_name,
              cast(:message as jsonb),
              0
            )
            """
        ),
        {"queue_name": PUSH_NOTIFICATIONS_QUEUE, "message": message},
    ).scalar_one()


def read_push_notification_messages(
    session: Session,
    *,
    visibility_timeout_seconds: int,
    batch_size: int = 10,
) -> list[PushNotificationMessage]:
    if not is_postgres_session(session):
        return []

    rows = (
        session.execute(
            text(
                """
                select msg_id, read_ct, message
                from pgmq.read(
                  :queue_name,
                  :visibility_timeout_seconds,
                  :batch_size
                )
                """
            ),
            {
                "queue_name": PUSH_NOTIFICATIONS_QUEUE,
                "visibility_timeout_seconds": visibility_timeout_seconds,
                "batch_size": batch_size,
            },
        )
        .mappings()
        .all()
    )

    messages: list[PushNotificationMessage] = []
    for row in rows:
        msg_id = int(row["msg_id"])
        try:
            body = parse_message_payload(row["message"])
            if body.get("v") != 1:
                raise ValueError(
                    f"unsupported push notification message version: {body.get('v')!r}"
                )
            source_id = parse_uuid(str(body["source_id"]))
        except (ValueError, KeyError) as exc:
            logger.warning(
                "Archiving malformed push notification queue message %s: %s", msg_id, exc
            )
            archive_push_notification_message(session, msg_id)
            continue
        messages.append(
            PushNotificationMessage(
                msg_id=msg_id,
                source_id=source_id,
                read_count=int(row["read_ct"]),
            )
        )
    return messages


def archive_push_notification_message(session: Session, msg_id: int) -> None:
    if not is_postgres_session(session):
        return

    archived = session.execute(
        text("select pgmq.archive(:queue_name, :msg_id)"),
        {"queue_name": PUSH_NOTIFICATIONS_QUEUE, "msg_id": msg_id},
    ).scalar_one()
    if not archived:
        raise RuntimeError(f"Could not archive push notification message {msg_id}")
