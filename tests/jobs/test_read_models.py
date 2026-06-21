from __future__ import annotations

from uuid import UUID

from sqlmodel import Session

from src.jobs.models import Job, JobStatus
from src.jobs.read_models import job_detail_response, job_list_response
from src.mentions.models import Mention


OWNER = UUID("00000000-0000-4000-8000-000000000001")


def test_job_list_response_maps_summary_fields(session: Session) -> None:
    job = Job(
        owner_id=OWNER,
        source_url="https://www.instagram.com/reel/LIST123/",
        thumbnail_url="https://instagram.example/thumb.jpg",
        source_creator_handle="reader.handle",
        status=JobStatus.DONE,
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    response = job_list_response(session, str(OWNER))

    assert len(response) == 1
    assert response[0].job_id == str(job.id)
    assert response[0].status == JobStatus.DONE
    assert response[0].source_url == job.source_url
    assert response[0].thumbnail_url == "https://instagram.example/thumb.jpg"
    assert response[0].source_creator_handle == "reader.handle"
    assert response[0].created_at == job.created_at


def test_job_detail_response_filters_deleted_mentions(session: Session) -> None:
    job = Job(
        owner_id=OWNER,
        source_url="https://www.instagram.com/reel/DETAIL123/",
        thumbnail_url="https://instagram.example/detail.jpg",
        source_creator_handle="reader.handle",
        status=JobStatus.DONE,
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    visible = Mention(
        owner_id=OWNER,
        job_id=job.id,
        title="Atomic Habits",
        author="James Clear",
        category="book",
        confidence=0.93,
        google_books_url="https://books.google.com/books?id=atomic",
        cover_image_url="https://books.google.com/thumb.jpg",
        source_url=job.source_url,
    )
    deleted = Mention(
        owner_id=OWNER,
        job_id=job.id,
        title="Deleted Book",
        category="book",
        source_url=job.source_url,
        is_deleted=True,
    )
    session.add(visible)
    session.add(deleted)
    session.commit()
    session.refresh(visible)

    response = job_detail_response(session, job)

    assert response.job_id == str(job.id)
    assert response.status == JobStatus.DONE
    assert response.source_url == job.source_url
    assert response.thumbnail_url == "https://instagram.example/detail.jpg"
    assert response.source_creator_handle == "reader.handle"
    assert len(response.mentions) == 1
    assert response.mentions[0].id == str(visible.id)
    assert response.mentions[0].title == "Atomic Habits"
    assert response.mentions[0].author == "James Clear"
    assert response.mentions[0].google_books_url == visible.google_books_url
    assert response.mentions[0].cover_image_url == visible.cover_image_url
