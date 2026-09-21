from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from src.config import Settings
from src.push.expo import PushDeliveryResult, PushDeliveryRetryableError
from src.push.models import PushToken
from src.push.queue import PushNotificationMessage
from src.push.service import SourcePushTarget
from src.push.worker import process_push_notification_message
from src.sources.models import SavedSource, Source, SourceStatus
from src.timeutils import utc_now

OWNER = UUID("00000000-0000-4000-8000-000000000001")
OTHER_OWNER = UUID("00000000-0000-4000-8000-000000000002")


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def _source(session: Session, *, status: SourceStatus, external_id: str = "PUSH") -> Source:
    source = Source(
        source_key=f"instagram:reel:{external_id}",
        platform="instagram",
        source_type="reel",
        external_id=external_id,
        canonical_url=f"https://www.instagram.com/reel/{external_id}/",
        status=status,
        processed_at=utc_now() if status in (SourceStatus.DONE, SourceStatus.FAILED) else None,
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


def test_push_worker_archives_missing_source(monkeypatch):
    engine = _engine()
    archived = []

    def fake_archive(_session: Session, msg_id: int) -> None:
        archived.append(msg_id)

    monkeypatch.setattr("src.push.worker.archive_push_notification_message", fake_archive)

    try:
        process_push_notification_message(
            PushNotificationMessage(msg_id=20, source_id=uuid4(), read_count=1),
            engine,
            Settings(),
        )
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == [20]


def test_push_worker_leaves_pending_source_unarchived(monkeypatch):
    engine = _engine()
    archived = []
    sent = []

    def fake_archive(_session: Session, msg_id: int) -> None:
        archived.append(msg_id)

    def fake_send(_source: Source, targets: list[SourcePushTarget]) -> PushDeliveryResult:
        sent.append(targets)
        return PushDeliveryResult(disabled_tokens=set())

    monkeypatch.setattr("src.push.worker.archive_push_notification_message", fake_archive)

    try:
        with Session(engine) as session:
            source = _source(session, status=SourceStatus.PENDING)

        process_push_notification_message(
            PushNotificationMessage(msg_id=21, source_id=source.id, read_count=1),
            engine,
            Settings(),
            send_notifications=fake_send,
        )
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == []
    assert sent == []


@pytest.mark.parametrize("status", [SourceStatus.DONE, SourceStatus.FAILED])
def test_push_worker_sends_to_every_owner_with_active_tokens_and_disables_invalid(
    monkeypatch, status: SourceStatus
):
    engine = _engine()
    archived = []
    sent = []

    def fake_archive(_session: Session, msg_id: int) -> None:
        archived.append(msg_id)

    def fake_send(source: Source, targets: list[SourcePushTarget]) -> PushDeliveryResult:
        sent.append((source.id, sorted(targets, key=lambda t: t.saved_source_id)))
        return PushDeliveryResult(disabled_tokens={"ExpoPushToken[invalid]"})

    monkeypatch.setattr("src.push.worker.archive_push_notification_message", fake_archive)

    try:
        with Session(engine) as session:
            source = _source(session, status=status)
            source_id = source.id
            saved_owner = SavedSource(owner_id=OWNER, source_id=source_id)
            saved_other = SavedSource(owner_id=OTHER_OWNER, source_id=source_id)
            session.add(saved_owner)
            session.add(saved_other)
            session.add(
                PushToken(owner_id=OWNER, expo_push_token="ExpoPushToken[valid]", platform="ios")
            )
            session.add(
                PushToken(
                    owner_id=OWNER, expo_push_token="ExpoPushToken[invalid]", platform="android"
                )
            )
            session.add(
                PushToken(
                    owner_id=OWNER,
                    expo_push_token="ExpoPushToken[disabled]",
                    platform="ios",
                    disabled_at=utc_now(),
                )
            )
            session.add(
                PushToken(
                    owner_id=OTHER_OWNER, expo_push_token="ExpoPushToken[other]", platform="ios"
                )
            )
            session.commit()
            session.refresh(saved_owner)
            session.refresh(saved_other)
            saved_owner_id = saved_owner.id
            saved_other_id = saved_other.id

        process_push_notification_message(
            PushNotificationMessage(msg_id=22, source_id=source_id, read_count=1),
            engine,
            Settings(),
            send_notifications=fake_send,
        )

        with Session(engine) as session:
            invalid = session.exec(
                select(PushToken).where(PushToken.expo_push_token == "ExpoPushToken[invalid]")
            ).one()
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == [22]
    assert len(sent) == 1
    sent_source_id, sent_targets = sent[0]
    assert sent_source_id == source_id
    tokens_by_saved_source = {
        target.saved_source_id: sorted(target.expo_push_tokens) for target in sent_targets
    }
    assert tokens_by_saved_source == {
        saved_owner_id: ["ExpoPushToken[invalid]", "ExpoPushToken[valid]"],
        saved_other_id: ["ExpoPushToken[other]"],
    }
    assert invalid.disabled_at is not None


def test_push_worker_retries_request_level_delivery_failure(monkeypatch):
    engine = _engine()
    archived = []

    def fake_archive(_session: Session, msg_id: int) -> None:
        archived.append(msg_id)

    def fake_send(_source: Source, _targets: list[SourcePushTarget]) -> PushDeliveryResult:
        raise PushDeliveryRetryableError("network down")

    monkeypatch.setattr("src.push.worker.archive_push_notification_message", fake_archive)

    try:
        with Session(engine) as session:
            source = _source(session, status=SourceStatus.DONE)
            source_id = source.id
            session.add(SavedSource(owner_id=OWNER, source_id=source_id))
            session.add(
                PushToken(owner_id=OWNER, expo_push_token="ExpoPushToken[valid]", platform="ios")
            )
            session.commit()

        process_push_notification_message(
            PushNotificationMessage(msg_id=23, source_id=source_id, read_count=1),
            engine,
            Settings(),
            send_notifications=fake_send,
        )
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == []


def test_push_worker_archives_poison_message_past_max_deliveries(monkeypatch):
    engine = _engine()
    archived = []
    sent = []

    def fake_archive(_session: Session, msg_id: int) -> None:
        archived.append(msg_id)

    def fake_send(_source: Source, targets: list[SourcePushTarget]) -> PushDeliveryResult:
        sent.append(targets)
        return PushDeliveryResult(disabled_tokens=set())

    monkeypatch.setattr("src.push.worker.archive_push_notification_message", fake_archive)

    try:
        with Session(engine) as session:
            source = _source(session, status=SourceStatus.DONE)

        process_push_notification_message(
            PushNotificationMessage(msg_id=24, source_id=source.id, read_count=11),
            engine,
            Settings(worker_queue_max_deliveries=5),
            send_notifications=fake_send,
        )
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == [24]
    assert sent == []
