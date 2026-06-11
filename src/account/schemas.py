from __future__ import annotations

from pydantic import BaseModel


class DeleteAccountResponse(BaseModel):
    deleted: bool
