from __future__ import annotations

from fastapi import APIRouter

from src.auth.dependencies import CallerDep
from src.jobs.dependencies import SessionDep
from src.push.schemas import (
    DisablePushTokenRequest,
    DisablePushTokenResponse,
    RegisterPushTokenRequest,
    RegisterPushTokenResponse,
)
from src.push.service import disable_push_token, register_push_token

router = APIRouter(tags=["push"])


@router.post("/v1/push-tokens")
async def register_token(
    body: RegisterPushTokenRequest,
    caller: CallerDep,
    session: SessionDep,
) -> RegisterPushTokenResponse:
    register_push_token(
        session,
        owner_id=caller.subject_id,
        expo_push_token=body.expo_push_token,
        platform=body.platform,
    )
    return RegisterPushTokenResponse(registered=True)


@router.post("/v1/push-tokens/disable")
async def disable_token(
    body: DisablePushTokenRequest,
    caller: CallerDep,
    session: SessionDep,
) -> DisablePushTokenResponse:
    disable_push_token(
        session,
        owner_id=caller.subject_id,
        expo_push_token=body.expo_push_token,
    )
    return DisablePushTokenResponse(disabled=True)
