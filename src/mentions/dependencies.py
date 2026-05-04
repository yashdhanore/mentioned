from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from src.auth.dependencies import CallerDep
from src.database import get_session
from src.mentions.exceptions import MentionNotFound
from src.mentions.models import Mention

SessionDep = Annotated[Session, Depends(get_session)]


async def valid_mention_id(mention_id: str, caller: CallerDep, session: SessionDep) -> Mention:
    mention = session.get(Mention, mention_id)
    if not mention or mention.owner_id != caller.subject_id or mention.is_deleted:
        raise MentionNotFound()
    return mention


ValidMentionDep = Annotated[Mention, Depends(valid_mention_id)]
