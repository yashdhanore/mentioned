from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from src.mentions.models import Mention


def list_mentions(
    session: Session,
    owner_id: str,
    limit: int = 50,
    cursor: str | None = None,
) -> list[Mention]:
    stmt = (
        select(Mention)
        .where(Mention.owner_id == owner_id, Mention.is_deleted == False)
        .order_by(Mention.created_at.desc())
        .limit(limit)
    )
    if cursor:
        stmt = stmt.where(Mention.id < cursor)
    return list(session.exec(stmt).all())


def get_mention(session: Session, mention_id: str) -> Mention | None:
    return session.get(Mention, mention_id)


def update_mention(session: Session, mention: Mention, **fields) -> Mention:
    for key, value in fields.items():
        if value is not None:
            setattr(mention, key, value)
    mention.updated_at = datetime.utcnow()
    session.add(mention)
    session.commit()
    session.refresh(mention)
    return mention


def delete_mention(session: Session, mention: Mention) -> None:
    mention.is_deleted = True
    mention.updated_at = datetime.utcnow()
    session.add(mention)
    session.commit()
