from __future__ import annotations

import logging

from sqlmodel import Session, delete
from supabase_auth.errors import AuthApiError

from src.config import Settings, get_settings
from src.ids import parse_uuid
from src.push.models import PushToken
from src.sources.models import SavedSource
from supabase import Client, create_client

logger = logging.getLogger(__name__)


class AuthAdminUnavailableError(RuntimeError):
    """Supabase auth is on, but the admin access needed to delete a login is not configured."""


def delete_account_data(session: Session, owner_id: str) -> None:
    """Hard-delete every row this user owns. Runs inside the caller's RLS context.

    The shared `sources`/`source_items` cache rows are left in place: other users
    may still have their own `saved_sources` row pointing at the same canonical
    source, and this cache carries no owner id to delete by.
    """
    owner_uuid = parse_uuid(owner_id)
    session.exec(delete(SavedSource).where(SavedSource.owner_id == owner_uuid))
    session.exec(delete(PushToken).where(PushToken.owner_id == owner_uuid))
    session.commit()


def get_auth_admin(settings: Settings | None = None) -> Client | None:
    """Return a Supabase admin client for deleting logins, check before any data is deleted."""
    settings = settings or get_settings()
    supabase_url = settings.auth.supabase_project_url
    service_role_key = settings.auth.supabase_service_role_key
    if supabase_url and service_role_key:
        return create_client(supabase_url, service_role_key)
    if settings.auth.auth_mode == "supabase":
        raise AuthAdminUnavailableError(
            "Deleting a login requires SUPABASE_PROJECT_URL and SUPABASE_SERVICE_ROLE_KEY"
        )
    return None


def delete_supabase_auth_user(admin: Client | None, owner_id: str) -> None:
    """Delete the Supabase login via the service-role admin API."""
    if admin is None:
        logger.info("Skipping Supabase auth user deletion because admin access is not configured")
        return
    try:
        admin.auth.admin.delete_user(owner_id)
    except AuthApiError as exc:
        if exc.code != "user_not_found":
            raise
