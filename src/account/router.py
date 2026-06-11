from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from src.account.schemas import DeleteAccountResponse
from src.account.service import delete_account_data, delete_supabase_auth_user
from src.auth.dependencies import CallerDep
from src.jobs.dependencies import SessionDep

router = APIRouter(tags=["account"])


@router.delete("/v1/account")
async def delete_account(
    caller: CallerDep,
    session: SessionDep,
) -> DeleteAccountResponse:
    # Delete owned data first: if the auth-user delete fails afterwards, the
    # login still works so the user can sign back in and retry. Deleting the
    # auth user first would orphan any data left behind on a partial failure.
    delete_account_data(session, caller.subject_id)

    try:
        delete_supabase_auth_user(caller.subject_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Account data was deleted but the login could not be removed. Please try again.",
        ) from exc

    return DeleteAccountResponse(deleted=True)
