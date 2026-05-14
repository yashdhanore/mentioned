from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Session, SQLModel, create_engine, select

from src.jobs.models import Job, JobStatus
from src.push.expo import PushDeliveryResult, PushDeliveryRetryableError
from src.push.models import PushToken
from src.push.queue import PushNotificationMessage
from src.worker import process_push_notification_message


OWNER = UUID("00000000-0000-4000-8000-000000000001")
OTHER_OWNER = UUID("00000000-0000-4000-8000-000000000002")


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def test_push_worker_archives_missing_job(monkeypatch):
    engine = _engine()
    archived = []

    def fake_archive(_session: Session, msg_id: int) -> None:
        archived.append(msg_id)

    monkeypatch.setattr("src.worker.archive_push_notification_message", fake_archive)

    try:
        process_push_notification_message(
            PushNotificationMessage(msg_id=20, job_id=uuid4(), read_count=1),
            engine,
        )
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == [20]


def test_push_worker_leaves_pending_job_unarchived(monkeypatch):
    engine = _engine()
    archived = []
    sent = []

    def fake_archive(_session: Session, msg_id: int) -> None:
        archived.append(msg_id)

    def fake_send(_job: Job, tokens: list[str]) -> PushDeliveryResult:
        sent.append(tokens)
        return PushDeliveryResult(disabled_tokens=set())

    monkeypatch.setattr("src.worker.archive_push_notification_message", fake_archive)
    monkeypatch.setattr("src.worker.send_job_push_notifications", fake_send)

    try:
        with Session(engine) as session:
            job = Job(
                owner_id=OWNER,
                source_url="https://www.instagram.com/reel/PENDING/",
                status=JobStatus.PENDING,
            )
            session.add(job)
            session.commit()
            session.refresh(job)

        process_push_notification_message(
            PushNotificationMessage(msg_id=21, job_id=job.id, read_count=1),
            engine,
        )
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == []
    assert sent == []


def test_push_worker_sends_active_owner_tokens_and_disables_invalid(monkeypatch):
    engine = _engine()
    archived = []
    sent = []

    def fake_archive(_session: Session, msg_id: int) -> None:
        archived.append(msg_id)

    def fake_send(job: Job, tokens: list[str]) -> PushDeliveryResult:
        sent.append((job.id, tokens))
        return PushDeliveryResult(disabled_tokens={"ExpoPushToken[invalid]"})

    monkeypatch.setattr("src.worker.archive_push_notification_message", fake_archive)
    monkeypatch.setattr("src.worker.send_job_push_notifications", fake_send)

    try:
        with Session(engine) as session:
            job = Job(
                owner_id=OWNER,
                source_url="https://www.instagram.com/reel/DONE/",
                status=JobStatus.DONE,
                finished_at=datetime.utcnow(),
            )
            session.add(job)
            session.add(
                PushToken(
                    owner_id=OWNER,
                    expo_push_token="ExpoPushToken[valid]",
                    platform="ios",
                )
            )
            session.add(
                PushToken(
                    owner_id=OWNER,
                    expo_push_token="ExpoPushToken[invalid]",
                    platform="android",
                )
            )
            session.add(
                PushToken(
                    owner_id=OWNER,
                    expo_push_token="ExpoPushToken[disabled]",
                    platform="ios",
                    disabled_at=datetime.utcnow(),
                )
            )
            session.add(
                PushToken(
                    owner_id=OTHER_OWNER,
                    expo_push_token="ExpoPushToken[other]",
                    platform="ios",
                )
            )
            session.commit()
            session.refresh(job)

        process_push_notification_message(
            PushNotificationMessage(msg_id=22, job_id=job.id, read_count=1),
            engine,
        )

        with Session(engine) as session:
            invalid = session.exec(
                select(PushToken).where(PushToken.expo_push_token == "ExpoPushToken[invalid]")
            ).one()
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == [22]
    assert sent == [
        (
            job.id,
            ["ExpoPushToken[valid]", "ExpoPushToken[invalid]"],
        )
    ]
    assert invalid.disabled_at is not None


def test_push_worker_retries_request_level_delivery_failure(monkeypatch):
    engine = _engine()
    archived = []

    def fake_archive(_session: Session, msg_id: int) -> None:
        archived.append(msg_id)

    def fake_send(_job: Job, _tokens: list[str]) -> PushDeliveryResult:
        raise PushDeliveryRetryableError("network down")

    monkeypatch.setattr("src.worker.archive_push_notification_message", fake_archive)
    monkeypatch.setattr("src.worker.send_job_push_notifications", fake_send)

    try:
        with Session(engine) as session:
            job = Job(
                owner_id=OWNER,
                source_url="https://www.instagram.com/reel/DONE/",
                status=JobStatus.DONE,
                finished_at=datetime.utcnow(),
            )
            session.add(job)
            session.add(
                PushToken(
                    owner_id=OWNER,
                    expo_push_token="ExpoPushToken[valid]",
                    platform="ios",
                )
            )
            session.commit()
            session.refresh(job)

        process_push_notification_message(
            PushNotificationMessage(msg_id=23, job_id=job.id, read_count=1),
            engine,
        )
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == []
