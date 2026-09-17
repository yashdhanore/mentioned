from __future__ import annotations

from uuid import UUID

import pytest
from sqlmodel import select

from src.push.models import PushToken
from src.timeutils import utc_now

pytestmark = pytest.mark.asyncio
TEST_USER_ID = "00000000-0000-4000-8000-000000000001"
TEST_USER_UUID = UUID(TEST_USER_ID)
OTHER_USER_UUID = UUID("00000000-0000-4000-8000-000000000002")


async def test_register_push_token_inserts_for_caller(client, session):
    resp = await client.post(
        "/v1/push-tokens",
        json={"expo_push_token": "ExpoPushToken[token-1]", "platform": "ios"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"registered": True}
    token = session.exec(select(PushToken)).one()
    assert token.owner_id == TEST_USER_UUID
    assert token.expo_push_token == "ExpoPushToken[token-1]"
    assert token.platform == "ios"
    assert token.disabled_at is None


async def test_register_push_token_updates_and_reenables_existing_token(client, session):
    token = PushToken(
        owner_id=TEST_USER_UUID,
        expo_push_token="ExpoPushToken[token-1]",
        platform="ios",
        disabled_at=utc_now(),
    )
    session.add(token)
    session.commit()
    session.refresh(token)
    previous_last_seen = token.last_seen_at

    resp = await client.post(
        "/v1/push-tokens",
        json={"expo_push_token": "ExpoPushToken[token-1]", "platform": "android"},
    )

    assert resp.status_code == 200
    session.expire_all()
    tokens = list(session.exec(select(PushToken)).all())
    assert len(tokens) == 1
    assert tokens[0].platform == "android"
    assert tokens[0].disabled_at is None
    assert tokens[0].last_seen_at >= previous_last_seen


async def test_disable_push_token_only_disables_caller_token(client, session):
    owner_token = PushToken(
        owner_id=TEST_USER_UUID,
        expo_push_token="ExpoPushToken[owner]",
        platform="ios",
    )
    other_token = PushToken(
        owner_id=OTHER_USER_UUID,
        expo_push_token="ExpoPushToken[other]",
        platform="ios",
    )
    session.add(owner_token)
    session.add(other_token)
    session.commit()

    resp = await client.post(
        "/v1/push-tokens/disable",
        json={"expo_push_token": "ExpoPushToken[owner]"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"disabled": True}
    session.refresh(owner_token)
    session.refresh(other_token)
    assert owner_token.disabled_at is not None
    assert other_token.disabled_at is None


async def test_disable_push_token_is_idempotent(client):
    resp = await client.post(
        "/v1/push-tokens/disable",
        json={"expo_push_token": "ExpoPushToken[missing]"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"disabled": True}
