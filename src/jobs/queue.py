from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlmodel import Session

from src.ids import parse_uuid

EXTRACT_JOBS_QUEUE = "extract_jobs"


@dataclass(frozen=True)
class ExtractJobMessage:
    msg_id: int
    job_id: UUID
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
    raise ValueError("extract job queue message must be a JSON object")


def enqueue_extract_job(session: Session, job_id: str | UUID) -> None:
    if not _is_postgres_session(session):
        return

    message = json.dumps({"v": 1, "job_id": str(job_id)})
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
        {"queue_name": EXTRACT_JOBS_QUEUE, "message": message},
    ).scalar_one()


def read_extract_job_messages(
    session: Session,
    *,
    visibility_timeout_seconds: int,
    max_poll_seconds: int,
    poll_interval_ms: int,
    batch_size: int = 1,
) -> list[ExtractJobMessage]:
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
                "queue_name": EXTRACT_JOBS_QUEUE,
                "visibility_timeout_seconds": visibility_timeout_seconds,
                "batch_size": batch_size,
                "max_poll_seconds": max_poll_seconds,
                "poll_interval_ms": poll_interval_ms,
            },
        )
        .mappings()
        .all()
    )

    messages = []
    for row in rows:
        body = _payload(row["message"])
        if body.get("v") != 1:
            raise ValueError("unsupported extract job queue message version")
        messages.append(
            ExtractJobMessage(
                msg_id=int(row["msg_id"]),
                job_id=parse_uuid(str(body["job_id"])),
                read_count=int(row["read_ct"]),
            )
        )
    return messages


def archive_extract_job_message(session: Session, msg_id: int) -> None:
    if not _is_postgres_session(session):
        return

    archived = session.execute(
        text("select pgmq.archive(:queue_name, :msg_id)"),
        {"queue_name": EXTRACT_JOBS_QUEUE, "msg_id": msg_id},
    ).scalar_one()
    if not archived:
        raise RuntimeError(f"Could not archive extract job queue message {msg_id}")
