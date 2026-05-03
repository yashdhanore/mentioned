from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.auth import Caller, get_current_caller
from app.db import get_session, set_rls_user_context


CallerDep = Annotated[Caller, Depends(get_current_caller)]
RawSessionDep = Annotated[Session, Depends(get_session)]


def get_authenticated_session(session: RawSessionDep, caller: CallerDep) -> Session:
    if caller.role == "user":
        set_rls_user_context(session, caller.subject_id)
    return session


SessionDep = Annotated[Session, Depends(get_authenticated_session)]
