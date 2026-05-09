from __future__ import annotations

from uuid import UUID

import pytest
from sqlmodel import Session, SQLModel, create_engine

from src.jobs.service import create_job
from src.mentions.models import Mention


pytestmark = pytest.mark.asyncio

OWNER = "00000000-0000-4000-8000-000000000001"
OWNER_UUID = UUID(OWNER)


async def test_list_mentions_empty(client):
    resp = await client.get("/v1/mentions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["next_cursor"] is None


async def test_patch_mention(client, session):
    job = create_job(session, OWNER, "https://instagram.com/reel/X/")
    m = Mention(
        owner_id=OWNER_UUID,
        job_id=job.id,
        title="Original",
        category="book",
        source_url="https://instagram.com/reel/X/",
    )
    session.add(m)
    session.commit()
    session.refresh(m)

    resp = await client.patch(f"/v1/mentions/{m.id}", json={"title": "Updated Title"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Title"


async def test_delete_mention(client, session):
    job = create_job(session, OWNER, "https://instagram.com/reel/X/")
    m = Mention(
        owner_id=OWNER_UUID,
        job_id=job.id,
        title="To Delete",
        category="book",
        source_url="https://instagram.com/reel/X/",
    )
    session.add(m)
    session.commit()
    session.refresh(m)

    resp = await client.delete(f"/v1/mentions/{m.id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


async def test_delete_mention_not_found(client):
    resp = await client.delete("/v1/mentions/00000000-0000-0000-0000-000000000099")
    assert resp.status_code == 404
