from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from src.waitlist.dependencies import SessionDep
from src.waitlist.schemas import WaitlistSignupRequest, WaitlistSignupResponse
from src.waitlist.service import create_or_update_signup


router = APIRouter(tags=["waitlist"])


@router.post("/v1/waitlist", status_code=status.HTTP_201_CREATED)
def create_waitlist_signup(
    body: WaitlistSignupRequest,
    request: Request,
    response: Response,
    session: SessionDep,
) -> WaitlistSignupResponse:
    signup, created = create_or_update_signup(
        session,
        email=str(body.email),
        source=body.source,
        user_agent=request.headers.get("user-agent"),
    )
    if not created:
        response.status_code = status.HTTP_200_OK

    return WaitlistSignupResponse(
        id=str(signup.id),
        email=signup.email,
        created=created,
        created_at=signup.created_at,
    )
