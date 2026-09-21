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

SOURCE_EXTRACTIONS_QUEUE = "extract_sources"


@dataclass(frozen=True)
class SourceExtractionMessage:
    msg_id: int
    source_id: UUID
    read_count: int


def enqueue_source_extraction(session: Session, source_id: str | UUID) -> None:
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
        {"queue_name": SOURCE_EXTRACTIONS_QUEUE, "message": message},
    ).scalar_one()


def read_source_extraction_messages(
    session: Session,
    *,
    visibility_timeout_seconds: int,
    max_poll_seconds: int,
    poll_interval_ms: int,
    batch_size: int = 1,
) -> list[SourceExtractionMessage]:
    if not is_postgres_session(session):
        return []

    rows = (
        session.execute(
            text(
                """
                select msg_id, read_ct, message
                from pgmq.read_with_poll(
                  :queue_name,
                  :visibility_timeout_seconds,
                  :batch_size,
                  :max_poll_seconds,
                  :poll_interval_ms,
                  '{}'::jsonb
                )
                """
            ),
            {
                "queue_name": SOURCE_EXTRACTIONS_QUEUE,
                "visibility_timeout_seconds": visibility_timeout_seconds,
                "batch_size": batch_size,
                "max_poll_seconds": max_poll_seconds,
                "poll_interval_ms": poll_interval_ms,
            },
        )
        .mappings()
        .all()
    )

    messages: list[SourceExtractionMessage] = []
    for row in rows:
        msg_id = int(row["msg_id"])
        try:
            body = parse_message_payload(row["message"])
            if body.get("v") != 1:
                raise ValueError(
                    f"unsupported source extraction message version: {body.get('v')!r}"
                )
            source_id = parse_uuid(str(body["source_id"]))
        except (ValueError, KeyError) as exc:
            logger.warning(
                "Archiving malformed source extraction queue message %s: %s", msg_id, exc
            )
            archive_source_extraction_message(session, msg_id)
            continue
        messages.append(
            SourceExtractionMessage(
                msg_id=msg_id,
                source_id=source_id,
                read_count=int(row["read_ct"]),
            )
        )
    return messages


def archive_source_extraction_message(session: Session, msg_id: int) -> None:
    if not is_postgres_session(session):
        return

    archived = session.execute(
        text("select pgmq.archive(:queue_name, :msg_id)"),
        {"queue_name": SOURCE_EXTRACTIONS_QUEUE, "msg_id": msg_id},
    ).scalar_one()
    if not archived:
        raise RuntimeError(f"Could not archive source extraction queue message {msg_id}")
