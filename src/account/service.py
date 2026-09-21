from __future__ import annotations

import logging

from sqlmodel import Session, delete

from src.config import Settings, get_settings
from src.ids import parse_uuid
from src.push.models import PushToken
from src.sources.models import SavedSource

try:
    from supabase import create_client
except ImportError:  # pragma: no cover - exercised only before dependencies are installed
    create_client = None


logger = logging.getLogger(__name__)


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


def delete_supabase_auth_user(owner_id: str, settings: Settings | None = None) -> bool:
    """Delete the Supabase auth user via the service-role admin API.

    Returns True when the user was deleted, False when Supabase admin access is
    not configured (e.g. local dev). Raises on unexpected admin API failures so
    the caller does not report a successful deletion that left the login intact.
    """
    settings = settings or get_settings()
    supabase_url = settings.auth.supabase_project_url
    service_role_key = settings.auth.supabase_service_role_key
    if not supabase_url or not service_role_key:
        logger.info("Skipping Supabase auth user deletion because admin access is not configured")
        return False
    if create_client is None:
        logger.warning("Skipping Supabase auth user deletion because supabase-py is not installed")
        return False

    client = create_client(supabase_url, service_role_key)
    client.auth.admin.delete_user(owner_id)
    return True
