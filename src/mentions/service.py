from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from src.ids import parse_uuid
from src.mentions.models import Mention
from src.timeutils import utc_now


def list_mentions(
    session: Session,
    owner_id: str,
    limit: int = 50,
    cursor: str | None = None,
) -> list[Mention]:
    owner_uuid = parse_uuid(owner_id)
    stmt = (
        select(Mention)
        .where(Mention.owner_id == owner_uuid, Mention.is_deleted.is_(False))
        .order_by(Mention.created_at.desc())
        .limit(limit)
    )
    if cursor:
        stmt = stmt.where(Mention.id < parse_uuid(cursor))
    return list(session.exec(stmt).all())


def get_mention(session: Session, mention_id: str | UUID) -> Mention | None:
    return session.get(Mention, parse_uuid(mention_id))


def update_mention(session: Session, mention: Mention, **fields) -> Mention:
    for key, value in fields.items():
        if value is not None:
            setattr(mention, key, value)
    mention.updated_at = utc_now()
    session.add(mention)
    session.commit()
    session.refresh(mention)
    return mention


def delete_mention(session: Session, mention: Mention) -> None:
    mention.is_deleted = True
    mention.updated_at = utc_now()
    session.add(mention)
    session.commit()
