from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlmodel import Session, select

from src.ids import parse_uuid
from src.push.models import PushToken
from src.sources.models import SavedSource
from src.timeutils import utc_now


@dataclass(frozen=True)
class SourcePushTarget:
    saved_source_id: UUID
    expo_push_tokens: list[str] = field(default_factory=list)


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


def list_push_targets_for_source(session: Session, source_id: UUID) -> list[SourcePushTarget]:
    stmt = (
        select(SavedSource.id, PushToken.expo_push_token)
        .join(PushToken, PushToken.owner_id == SavedSource.owner_id)
        .where(SavedSource.source_id == source_id, PushToken.disabled_at.is_(None))
    )
    tokens_by_saved_source: dict[UUID, list[str]] = {}
    for saved_source_id, expo_push_token in session.exec(stmt).all():
        tokens_by_saved_source.setdefault(saved_source_id, []).append(expo_push_token)
    return [
        SourcePushTarget(saved_source_id=saved_source_id, expo_push_tokens=tokens)
        for saved_source_id, tokens in tokens_by_saved_source.items()
    ]


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
