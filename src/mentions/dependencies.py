from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from src.auth.dependencies import AuthenticatedSessionDep, CallerDep
from src.ids import parse_uuid
from src.mentions.exceptions import MentionNotFound
from src.mentions.models import Mention

SessionDep = AuthenticatedSessionDep


async def valid_mention_id(mention_id: str, caller: CallerDep, session: SessionDep) -> Mention:
    try:
        mention_uuid = parse_uuid(mention_id)
        caller_uuid = parse_uuid(caller.subject_id)
    except ValueError as exc:
        raise MentionNotFound() from exc
    mention = session.get(Mention, mention_uuid)
    if not mention or mention.owner_id != caller_uuid or mention.is_deleted:
        raise MentionNotFound()
    return mention


ValidMentionDep = Annotated[Mention, Depends(valid_mention_id)]
