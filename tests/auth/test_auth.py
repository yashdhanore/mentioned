from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.auth.dependencies import get_current_caller
from src.config import get_settings
from src.main import app

pytestmark = pytest.mark.asyncio


async def test_health_no_auth():
    """Health endpoint should work without auth."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_dev_mode_default_user():
    """In dev mode, the real get_current_caller dependency uses the default user."""
    settings = get_settings()
    assert settings.auth.auth_mode == "dev"

    caller = get_current_caller(authorization=None)

    assert caller.subject_id == settings.auth.dev_user_id
    assert caller.role == "user"


async def test_dev_mode_dev_prefixed_token_overrides_user():
    """In dev mode, an explicit `dev:<uuid>` bearer token simulates that user."""
    caller = get_current_caller(authorization="Bearer dev:11111111-1111-4111-8111-111111111111")

    assert caller.subject_id == "11111111-1111-4111-8111-111111111111"
    assert caller.role == "user"
