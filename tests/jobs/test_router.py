from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

import pytest

from src.books.models import Book
from src.config import Settings
from src.jobs.models import Job, JobStatus
from src.mentions.models import Mention


pytestmark = pytest.mark.asyncio
TEST_USER_ID = "00000000-0000-4000-8000-000000000001"
TEST_USER_UUID = UUID(TEST_USER_ID)


def _quota_settings() -> Settings:
    return Settings(
        max_job_create_burst_per_minute=3,
        max_jobs_created_per_day=25,
        max_active_jobs_per_user=5,
    )


async def test_create_job(client):
    resp = await client.post("/v1/jobs", json={"url": "https://www.instagram.com/reel/ABC123/"})
    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "pending"


async def test_create_job_burst_limit(client, session, monkeypatch):
    monkeypatch.setattr("src.jobs.router.get_settings", _quota_settings)
    now = datetime.utcnow()
    for index in range(3):
        session.add(
            Job(
                owner_id=TEST_USER_UUID,
                source_url=f"https://www.instagram.com/reel/BURST{index}/",
                status=JobStatus.DONE,
                created_at=now - timedelta(seconds=index),
            )
        )
    session.commit()

    resp = await client.post("/v1/jobs", json={"url": "https://www.instagram.com/reel/ABC123/"})

    assert resp.status_code == 429
    assert resp.json()["error_code"] == "rate_limited"


async def test_create_job_daily_quota(client, session, monkeypatch):
    monkeypatch.setattr("src.jobs.router.get_settings", _quota_settings)
    now = datetime.utcnow()
    for index in range(25):
        session.add(
            Job(
                owner_id=TEST_USER_UUID,
                source_url=f"https://www.instagram.com/reel/DAILY{index}/",
                status=JobStatus.DONE,
                created_at=now - timedelta(hours=2, minutes=index),
            )
        )
    session.commit()

    resp = await client.post("/v1/jobs", json={"url": "https://www.instagram.com/reel/ABC123/"})

    assert resp.status_code == 429
    assert resp.json()["error_code"] == "quota_exceeded"


async def test_create_job_active_quota(client, session, monkeypatch):
    monkeypatch.setattr("src.jobs.router.get_settings", _quota_settings)
    now = datetime.utcnow() - timedelta(hours=2)
    for index in range(5):
        session.add(
            Job(
                owner_id=TEST_USER_UUID,
                source_url=f"https://www.instagram.com/reel/ACTIVE{index}/",
                status=JobStatus.PENDING,
                created_at=now - timedelta(minutes=index),
            )
        )
    session.commit()

    resp = await client.post("/v1/jobs", json={"url": "https://www.instagram.com/reel/ABC123/"})

    assert resp.status_code == 429
    assert resp.json()["error_code"] == "quota_exceeded"


async def test_create_job_invalid_url(client):
    resp = await client.post("/v1/jobs", json={"url": "https://example.com/foo"})
    assert resp.status_code in (400, 404)


async def test_list_jobs_empty(client):
    resp = await client.get("/v1/jobs")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_jobs_returns_thumbnail_url(client, session):
    job = Job(
        owner_id=TEST_USER_UUID,
        source_url="https://www.instagram.com/reel/LIST123/",
        thumbnail_url="https://instagram.example/list-thumb.jpg",
        source_creator_handle="jamesclear",
        status=JobStatus.DONE,
    )
    session.add(job)
    session.commit()

    resp = await client.get("/v1/jobs")

    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["job_id"] == str(job.id)
    assert data[0]["thumbnail_url"] == "https://instagram.example/list-thumb.jpg"
    assert data[0]["source_creator_handle"] == "jamesclear"


async def test_get_job(client):
    create_resp = await client.post("/v1/jobs", json={"url": "https://www.instagram.com/reel/ABC123/"})
    job_id = create_resp.json()["job_id"]

    resp = await client.get(f"/v1/jobs/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == job_id
    assert data["status"] == "pending"
    assert data["mentions"] == []


async def test_get_job_returns_linked_book_id_and_existing_flat_fields(client, session):
    book = Book(
        provider_volume_id="google-volume-1",
        title="Atomic Habits",
        authors=["James Clear"],
        cover_image_url="https://books.google.com/thumb.jpg",
        info_link="https://books.google.com/books?id=google-volume-1",
    )
    session.add(book)
    session.commit()
    session.refresh(book)

    job = Job(
        owner_id=TEST_USER_UUID,
        source_url="https://www.instagram.com/reel/BOOK123/",
        thumbnail_url="https://instagram.example/thumb.jpg",
        source_creator_handle="jamesclear",
        status=JobStatus.DONE,
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    session.add(
        Mention(
            owner_id=TEST_USER_UUID,
            job_id=job.id,
            book_id=book.id,
            title="Atomic Habits",
            author="James Clear",
            category="book",
            confidence=0.93,
            google_books_url=book.info_link,
            cover_image_url=book.cover_image_url,
            source_url=job.source_url,
        )
    )
    session.commit()

    resp = await client.get(f"/v1/jobs/{job.id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["thumbnail_url"] == "https://instagram.example/thumb.jpg"
    assert data["source_creator_handle"] == "jamesclear"
    mention = data["mentions"][0]
    assert mention["book_id"] == str(book.id)
    assert mention["title"] == "Atomic Habits"
    assert mention["author"] == "James Clear"
    assert mention["google_books_url"] == book.info_link
    assert mention["cover_image_url"] == book.cover_image_url


async def test_get_job_not_found(client):
    resp = await client.get("/v1/jobs/00000000-0000-0000-0000-000000000099")
    assert resp.status_code == 404
