from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, SQLModel, create_engine, select

from src.books.models import Book
from src.extraction.schemas import ExtractedMention, GoogleBook, PipelineResult
from src.jobs.models import Job, JobStatus
from src.mentions.models import Mention
from src.worker import process_job


OWNER = UUID("00000000-0000-4000-8000-000000000001")


def test_worker_links_book_mentions_to_deduplicated_google_book(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    try:
        async def find_google_book(_title: str, _author: str | None) -> GoogleBook:
            return GoogleBook(
                provider_volume_id="google-volume-1",
                provider_etag="etag-1",
                provider_self_link="https://www.googleapis.com/books/v1/volumes/google-volume-1",
                title="Atomic Habits",
                authors=["James Clear"],
                industry_identifiers=[
                    {"type": "ISBN_13", "identifier": "9780735211292"},
                    {"type": "ISBN_10", "identifier": "0735211299"},
                ],
                image_links={"thumbnail": "https://books.google.com/thumb.jpg"},
                cover_image_url="https://books.google.com/thumb.jpg",
                info_link="https://books.google.com/books?id=google-volume-1",
                canonical_volume_link="https://books.google.com/books/about/Atomic_Habits.html?id=google-volume-1",
                raw_provider_payload={"id": "google-volume-1"},
            )

        monkeypatch.setattr(
            "src.worker.run_pipeline",
            lambda _url: PipelineResult(
                thumbnail_url="https://instagram.example/reel.jpg",
                source_creator_handle="jamesclear",
                mentions=[
                    ExtractedMention(
                        title="Atomic Habits",
                        author="James Clear",
                        category="book",
                        confidence=0.9,
                    ),
                    ExtractedMention(
                        title="Atomic Habits",
                        author="James Clear",
                        category="book",
                        confidence=0.82,
                    ),
                ]
            ),
        )
        monkeypatch.setattr(
            "src.worker.store_job_thumbnail",
            lambda _url, *, owner_id, job_id: "https://example.supabase.co/storage/v1/object/public/job-thumbnails/reel.jpg",
        )
        monkeypatch.setattr("src.worker.find_google_book", find_google_book)

        with Session(engine) as session:
            job = Job(
                owner_id=OWNER,
                source_url="https://www.instagram.com/reel/BOOK123/",
                status=JobStatus.PENDING,
            )
            session.add(job)
            session.commit()
            session.refresh(job)

            process_job(job, session)

            books = list(session.exec(select(Book)).all())
            mentions = list(session.exec(select(Mention)).all())
            refreshed_job = session.get(Job, job.id)

        assert len(books) == 1
        assert books[0].provider_volume_id == "google-volume-1"
        assert books[0].isbn_13 == "9780735211292"
        assert len(mentions) == 2
        assert refreshed_job.thumbnail_url == "https://example.supabase.co/storage/v1/object/public/job-thumbnails/reel.jpg"
        assert refreshed_job.source_creator_handle == "jamesclear"
        assert {mention.book_id for mention in mentions} == {books[0].id}
        assert {mention.google_books_url for mention in mentions} == {books[0].info_link}
        assert {mention.cover_image_url for mention in mentions} == {books[0].cover_image_url}
    finally:
        SQLModel.metadata.drop_all(engine)


def test_worker_persists_thumbnail_when_pipeline_fails(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    try:
        monkeypatch.setattr(
            "src.worker.run_pipeline",
            lambda _url: PipelineResult(
                thumbnail_url="https://instagram.example/reel.jpg",
                source_creator_handle="jamesclear",
                error="Extraction failed",
            ),
        )
        monkeypatch.setattr(
            "src.worker.store_job_thumbnail",
            lambda _url, *, owner_id, job_id: "https://example.supabase.co/storage/v1/object/public/job-thumbnails/reel.jpg",
        )

        with Session(engine) as session:
            job = Job(
                owner_id=OWNER,
                source_url="https://www.instagram.com/reel/BOOK123/",
                status=JobStatus.PENDING,
            )
            session.add(job)
            session.commit()
            session.refresh(job)

            process_job(job, session)

            refreshed_job = session.get(Job, job.id)
            mentions = list(session.exec(select(Mention)).all())

        assert refreshed_job.status == JobStatus.FAILED
        assert refreshed_job.thumbnail_url == "https://example.supabase.co/storage/v1/object/public/job-thumbnails/reel.jpg"
        assert refreshed_job.source_creator_handle == "jamesclear"
        assert mentions == []
    finally:
        SQLModel.metadata.drop_all(engine)


def test_worker_completes_when_thumbnail_storage_fails(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    try:
        monkeypatch.setattr(
            "src.worker.run_pipeline",
            lambda _url: PipelineResult(
                thumbnail_url="https://instagram.example/reel.jpg",
                mentions=[
                    ExtractedMention(
                        title="Atomic Habits",
                        author="James Clear",
                        category="book",
                        confidence=0.9,
                    ),
                ],
            ),
        )
        monkeypatch.setattr(
            "src.worker.store_job_thumbnail",
            lambda _url, *, owner_id, job_id: None,
        )
        monkeypatch.setattr("src.worker.find_google_book", lambda _title, _author: None)

        with Session(engine) as session:
            job = Job(
                owner_id=OWNER,
                source_url="https://www.instagram.com/reel/BOOK123/",
                status=JobStatus.PENDING,
            )
            session.add(job)
            session.commit()
            session.refresh(job)

            process_job(job, session)

            refreshed_job = session.get(Job, job.id)
            mentions = list(session.exec(select(Mention)).all())

        assert refreshed_job.status == JobStatus.DONE
        assert refreshed_job.thumbnail_url is None
        assert len(mentions) == 1
    finally:
        SQLModel.metadata.drop_all(engine)
