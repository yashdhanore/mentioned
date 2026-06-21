from __future__ import annotations

from dataclasses import dataclass
import json
from uuid import UUID

from sqlalchemy import text
from sqlmodel import Session

from src.ids import parse_uuid


SOURCE_EXTRACTIONS_QUEUE = "extract_sources"


@dataclass(frozen=True)
class SourceExtractionMessage:
    msg_id: int
    source_id: UUID
    read_count: int


def _is_postgres_session(session: Session) -> bool:
    bind = session.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


def _payload(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("source extraction queue message must be a JSON object")


def enqueue_source_extraction(session: Session, source_id: str | UUID) -> None:
    if not _is_postgres_session(session):
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
    if not _is_postgres_session(session):
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
        body = _payload(row["message"])
        if body.get("v") != 1:
            raise ValueError("unsupported source extraction queue message version")
        messages.append(
            SourceExtractionMessage(
                msg_id=int(row["msg_id"]),
                source_id=parse_uuid(str(body["source_id"])),
                read_count=int(row["read_ct"]),
            )
        )
    return messages


def archive_source_extraction_message(session: Session, msg_id: int) -> None:
    if not _is_postgres_session(session):
        return

    archived = session.execute(
        text("select pgmq.archive(:queue_name, :msg_id)"),
        {"queue_name": SOURCE_EXTRACTIONS_QUEUE, "msg_id": msg_id},
    ).scalar_one()
    if not archived:
        raise RuntimeError(f"Could not archive source extraction queue message {msg_id}")
