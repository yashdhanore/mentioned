from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


async def test_create_job(client):
    resp = await client.post("/v1/jobs", json={"url": "https://www.instagram.com/reel/ABC123/"})
    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "pending"


async def test_create_job_invalid_url(client):
    resp = await client.post("/v1/jobs", json={"url": "https://example.com/foo"})
    assert resp.status_code in (400, 404)


async def test_list_jobs_empty(client):
    resp = await client.get("/v1/jobs")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_job(client):
    create_resp = await client.post("/v1/jobs", json={"url": "https://www.instagram.com/reel/ABC123/"})
    job_id = create_resp.json()["job_id"]

    resp = await client.get(f"/v1/jobs/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == job_id
    assert data["status"] == "pending"
    assert data["mentions"] == []


async def test_get_job_not_found(client):
    resp = await client.get("/v1/jobs/00000000-0000-0000-0000-000000000099")
    assert resp.status_code == 404
