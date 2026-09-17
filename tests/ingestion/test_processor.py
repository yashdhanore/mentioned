from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from src.books.models import Book
from src.books.schemas import GoogleBook
from src.extraction.schemas import ExtractedMention, PipelineResult
from src.ingestion.processor import SavedSourceIngestion
from src.jobs.models import Job, JobStatus
from src.mentions.models import Mention

OWNER = UUID("00000000-0000-4000-8000-000000000001")


def _job(session: Session) -> Job:
    job = Job(
        owner_id=OWNER,
        source_url="https://www.instagram.com/reel/BOOK123/",
        status=JobStatus.PENDING,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def _google_book() -> GoogleBook:
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


def test_processor_links_book_mentions_to_deduplicated_google_book(session: Session):
    ingestion = SavedSourceIngestion(
        extraction_runner=lambda _url: PipelineResult(
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
            ],
        ),
        thumbnail_store=lambda _url, *, owner_id, job_id: (
            "https://example.supabase.co/storage/v1/object/public/job-thumbnails/reel.jpg"
        ),
        book_finder=lambda _title, _author: _google_book(),
    )
    job = _job(session)

    ingestion.process_job(session, job)

    books = list(session.exec(select(Book)).all())
    mentions = list(session.exec(select(Mention)).all())
    refreshed_job = session.get(Job, job.id)

    assert refreshed_job is not None
    assert refreshed_job.status == JobStatus.DONE
    assert refreshed_job.thumbnail_url == (
        "https://example.supabase.co/storage/v1/object/public/job-thumbnails/reel.jpg"
    )
    assert refreshed_job.source_creator_handle == "jamesclear"
    assert len(books) == 1
    assert books[0].provider_volume_id == "google-volume-1"
    assert books[0].isbn_13 == "9780735211292"
    assert len(mentions) == 2
    assert {mention.book_id for mention in mentions} == {books[0].id}
    assert {mention.google_books_url for mention in mentions} == {books[0].info_link}
    assert {mention.cover_image_url for mention in mentions} == {books[0].cover_image_url}


def test_processor_persists_thumbnail_and_creator_handle_when_pipeline_fails(session: Session):
    ingestion = SavedSourceIngestion(
        extraction_runner=lambda _url: PipelineResult(
            thumbnail_url="https://instagram.example/reel.jpg",
            source_creator_handle="jamesclear",
            error="Extraction failed",
        ),
        thumbnail_store=lambda _url, *, owner_id, job_id: (
            "https://example.supabase.co/storage/v1/object/public/job-thumbnails/reel.jpg"
        ),
        book_finder=lambda _title, _author: None,
    )
    job = _job(session)

    ingestion.process_job(session, job)

    refreshed_job = session.get(Job, job.id)
    mentions = list(session.exec(select(Mention)).all())

    assert refreshed_job is not None
    assert refreshed_job.status == JobStatus.FAILED
    assert refreshed_job.error_message == "Extraction failed"
    assert refreshed_job.thumbnail_url == (
        "https://example.supabase.co/storage/v1/object/public/job-thumbnails/reel.jpg"
    )
    assert refreshed_job.source_creator_handle == "jamesclear"
    assert mentions == []


def test_processor_completes_when_thumbnail_storage_returns_none(session: Session):
    ingestion = SavedSourceIngestion(
        extraction_runner=lambda _url: PipelineResult(
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
        thumbnail_store=lambda _url, *, owner_id, job_id: None,
        book_finder=lambda _title, _author: None,
    )
    job = _job(session)

    ingestion.process_job(session, job)

    refreshed_job = session.get(Job, job.id)
    mentions = list(session.exec(select(Mention)).all())

    assert refreshed_job is not None
    assert refreshed_job.status == JobStatus.DONE
    assert refreshed_job.thumbnail_url is None
    assert len(mentions) == 1


def test_processor_passes_non_book_mentions_without_google_books_enrichment(session: Session):
    book_finder_calls: list[tuple[str, str | None]] = []

    def book_finder(title: str, author: str | None) -> GoogleBook | None:
        book_finder_calls.append((title, author))
        return _google_book()

    ingestion = SavedSourceIngestion(
        extraction_runner=lambda _url: PipelineResult(
            mentions=[
                ExtractedMention(
                    title="Copenhagen Coffee Lab",
                    category="place",
                    confidence=0.72,
                ),
            ],
        ),
        thumbnail_store=lambda _url, *, owner_id, job_id: None,
        book_finder=book_finder,
    )
    job = _job(session)

    ingestion.process_job(session, job)

    books = list(session.exec(select(Book)).all())
    mentions = list(session.exec(select(Mention)).all())

    assert books == []
    assert book_finder_calls == []
    assert len(mentions) == 1
    assert mentions[0].title == "Copenhagen Coffee Lab"
    assert mentions[0].category == "place"
    assert mentions[0].book_id is None
