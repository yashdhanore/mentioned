from __future__ import annotations

from uuid import UUID

import pytest
from sqlmodel import Session, select

from src.push.models import PushToken
from src.sources.models import SavedSource, Source, SourceStatus

TEST_USER_ID = "00000000-0000-4000-8000-000000000001"
TEST_USER_UUID = UUID(TEST_USER_ID)
OTHER_USER_UUID = UUID("00000000-0000-4000-8000-000000000002")


def _save_source(session: Session, external_id: str, *, owner_id: UUID) -> SavedSource:
    source_key = f"instagram:reel:{external_id}"
    source = session.exec(select(Source).where(Source.source_key == source_key)).first()
    if source is None:
        source = Source(
            source_key=source_key,
            platform="instagram",
            source_type="reel",
            external_id=external_id,
            canonical_url=f"https://www.instagram.com/reel/{external_id}/",
            status=SourceStatus.DONE,
        )
        session.add(source)
        session.commit()
        session.refresh(source)

    saved = SavedSource(owner_id=owner_id, source_id=source.id)
    session.add(saved)
    session.commit()
    session.refresh(saved)
    return saved


@pytest.fixture(autouse=True)
def no_supabase_admin_access(monkeypatch):
    # Dev auth without admin access: the real deletion path skips the login, which has no
    # Supabase counterpart here. Login deletion is covered in tests/e2e/test_account_deletion.py.
    monkeypatch.setattr("src.account.router.get_auth_admin", lambda: None)


async def test_delete_account_removes_saved_sources_and_push_tokens(
    client, session: Session
) -> None:
    _save_source(session, "DELETEME", owner_id=TEST_USER_UUID)
    session.add(
        PushToken(owner_id=TEST_USER_UUID, expo_push_token="ExpoPushToken[mine]", platform="ios")
    )
    session.commit()

    resp = await client.delete("/v1/account")

    assert resp.status_code == 200
    assert resp.json() == {"deleted": True}
    assert (
        session.exec(select(SavedSource).where(SavedSource.owner_id == TEST_USER_UUID)).first()
        is None
    )
    assert (
        session.exec(select(PushToken).where(PushToken.owner_id == TEST_USER_UUID)).first() is None
    )


async def test_delete_account_leaves_shared_source_when_another_user_still_has_it_saved(
    client, session: Session
) -> None:
    saved = _save_source(session, "SHARED", owner_id=TEST_USER_UUID)
    other_saved = _save_source(session, "SHARED", owner_id=OTHER_USER_UUID)
    assert other_saved.source_id == saved.source_id
    source_id = saved.source_id
    saved_id = saved.id
    other_saved_id = other_saved.id

    resp = await client.delete("/v1/account")
    session.expire_all()

    assert resp.status_code == 200
    assert session.get(Source, source_id) is not None
    assert (
        session.exec(select(SavedSource.id).where(SavedSource.id == other_saved_id)).first()
        is not None
    )
    assert session.exec(select(SavedSource.id).where(SavedSource.id == saved_id)).first() is None


async def test_delete_account_does_not_affect_other_users_data(client, session: Session) -> None:
    _save_source(session, "MINE", owner_id=TEST_USER_UUID)
    other_saved = _save_source(session, "OTHER", owner_id=OTHER_USER_UUID)
    other_saved_id = other_saved.id
    session.add(
        PushToken(owner_id=OTHER_USER_UUID, expo_push_token="ExpoPushToken[other]", platform="ios")
    )
    session.commit()

    resp = await client.delete("/v1/account")
    session.expire_all()

    assert resp.status_code == 200
    assert session.get(SavedSource, other_saved_id) is not None
    assert (
        session.exec(select(PushToken).where(PushToken.owner_id == OTHER_USER_UUID)).first()
        is not None
    )
