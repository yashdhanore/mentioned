from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.auth.dependencies import get_current_caller
from src.auth.schemas import Caller
from src.main import app


pytestmark = pytest.mark.asyncio


async def test_health_no_auth():
    """Health endpoint should work without auth."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_dev_mode_default_user(client):
    """In dev mode, requests without auth use the default user."""
    resp = await client.get("/v1/jobs")
    assert resp.status_code == 200
