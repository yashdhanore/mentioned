from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from src.auth.schemas import Caller
from src.auth.supabase import verify_supabase_token
from src.config import get_settings


def _bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.casefold() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
        )
    return token


def get_current_caller(authorization: str | None = Header(default=None)) -> Caller:
    settings = get_settings()
    auth = settings.auth
    if auth.auth_mode == "dev":
        if authorization is None:
            return Caller(subject_id=auth.dev_user_id, role="user")
        token = _bearer_token(authorization)
        if token.startswith("dev:"):
            return Caller(subject_id=token.removeprefix("dev:"), role="user")
        return Caller(subject_id=auth.dev_user_id, role="user")
    if auth.auth_mode != "supabase":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unsupported auth mode",
        )
    return verify_supabase_token(_bearer_token(authorization), auth)


def worker_caller(worker_id: str = "worker") -> Caller:
    return Caller(subject_id=worker_id, role="worker")


CallerDep = Annotated[Caller, Depends(get_current_caller)]
