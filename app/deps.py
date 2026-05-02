from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.auth import Caller, get_current_caller
from app.db import get_session


SessionDep = Annotated[Session, Depends(get_session)]
CallerDep = Annotated[Caller, Depends(get_current_caller)]
