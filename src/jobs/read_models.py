from __future__ import annotations

from sqlmodel import Session, select

from src.ids import parse_uuid
from src.jobs.models import Job
from src.jobs.schemas import JobListItem, JobResponse, MentionInJob
from src.mentions.models import Mention


def job_list_response(session: Session, owner_id: str, limit: int = 50) -> list[JobListItem]:
    owner_uuid = parse_uuid(owner_id)
    stmt = (
        select(Job)
        .where(Job.owner_id == owner_uuid)
        .order_by(Job.created_at.desc())
        .limit(limit)
    )
    jobs = list(session.exec(stmt).all())
    return [
        JobListItem(
            job_id=str(job.id),
            status=job.status,
            source_url=job.source_url,
            thumbnail_url=job.thumbnail_url,
            source_creator_handle=job.source_creator_handle,
            created_at=job.created_at,
        )
        for job in jobs
    ]


def job_detail_response(session: Session, job: Job) -> JobResponse:
    mentions = list(
        session.exec(
            select(Mention).where(Mention.job_id == job.id, Mention.is_deleted == False)
        ).all()
    )
    return JobResponse(
        job_id=str(job.id),
        status=job.status,
        source_url=job.source_url,
        thumbnail_url=job.thumbnail_url,
        source_creator_handle=job.source_creator_handle,
        error_message=job.error_message,
        created_at=job.created_at,
        finished_at=job.finished_at,
        mentions=[
            MentionInJob(
                id=str(mention.id),
                book_id=str(mention.book_id) if mention.book_id else None,
                title=mention.title,
                author=mention.author,
                category=mention.category,
                confidence=mention.confidence,
                google_books_url=mention.google_books_url,
                cover_image_url=mention.cover_image_url,
            )
            for mention in mentions
        ],
    )
