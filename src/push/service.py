from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from src.ids import parse_uuid
from src.push.models import PushToken
from src.timeutils import utc_now


def register_push_token(
    session: Session,
    *,
    owner_id: str,
    expo_push_token: str,
    platform: str,
) -> PushToken:
    owner_uuid = parse_uuid(owner_id)
    now = utc_now()
    stmt = select(PushToken).where(
        PushToken.owner_id == owner_uuid,
        PushToken.expo_push_token == expo_push_token,
    )
    token = session.exec(stmt).first()
    if token:
        token.platform = platform
        token.last_seen_at = now
        token.disabled_at = None
    else:
        token = PushToken(
            owner_id=owner_uuid,
            expo_push_token=expo_push_token,
            platform=platform,
            last_seen_at=now,
            created_at=now,
        )

    session.add(token)
    session.commit()
    session.refresh(token)
    return token


def disable_push_token(
    session: Session,
    *,
    owner_id: str,
    expo_push_token: str,
) -> bool:
    owner_uuid = parse_uuid(owner_id)
    stmt = select(PushToken).where(
        PushToken.owner_id == owner_uuid,
        PushToken.expo_push_token == expo_push_token,
        PushToken.disabled_at.is_(None),
    )
    token = session.exec(stmt).first()
    if not token:
        return False

    token.disabled_at = utc_now()
    session.add(token)
    session.commit()
    return True


def list_active_push_tokens(session: Session, owner_id: UUID) -> list[str]:
    stmt = (
        select(PushToken.expo_push_token)
        .where(
            PushToken.owner_id == owner_id,
            PushToken.disabled_at.is_(None),
        )
        .order_by(PushToken.created_at)
    )
    return list(session.exec(stmt).all())


def disable_push_token_value(session: Session, expo_push_token: str) -> bool:
    stmt = select(PushToken).where(
        PushToken.expo_push_token == expo_push_token,
        PushToken.disabled_at.is_(None),
    )
    tokens = list(session.exec(stmt).all())
    if not tokens:
        return False

    now = utc_now()
    for token in tokens:
        token.disabled_at = now
        session.add(token)
    return True
