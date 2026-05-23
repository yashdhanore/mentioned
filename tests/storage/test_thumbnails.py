from __future__ import annotations

from uuid import UUID

import httpx
import respx

from src.config import AuthConfig, Settings
from src.storage.thumbnails import store_job_thumbnail


OWNER_ID = UUID("00000000-0000-4000-8000-000000000001")
JOB_ID = UUID("11111111-1111-4111-8111-111111111111")
RAW_URL = "https://scontent.cdninstagram.com/v/t51.2885-15/thumbnail.jpg"


class FakeBucket:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, bytes, dict[str, str]]] = []

    def upload(self, *, path: str, file: bytes, file_options: dict[str, str]) -> None:
        self.uploads.append((path, file, file_options))

    def get_public_url(self, path: str) -> str:
        return f"https://example.supabase.co/storage/v1/object/public/job-thumbnails/{path}"


class FakeStorage:
    def __init__(self, bucket: FakeBucket) -> None:
        self.bucket = bucket
        self.bucket_name: str | None = None

    def from_(self, bucket_name: str) -> FakeBucket:
        self.bucket_name = bucket_name
        return self.bucket


class FakeSupabaseClient:
    def __init__(self, bucket: FakeBucket) -> None:
        self.storage = FakeStorage(bucket)


def settings_with_storage_key() -> Settings:
    return Settings(
        auth=AuthConfig(
            supabase_project_url="https://example.supabase.co",
            supabase_service_role_key="service-role-key",
        )
    )


@respx.mock
def test_store_job_thumbnail_uploads_valid_cdn_image(monkeypatch):
    bucket = FakeBucket()
    monkeypatch.setattr(
        "src.storage.thumbnails.create_client",
        lambda _url, _key: FakeSupabaseClient(bucket),
    )
    respx.get(RAW_URL).mock(
        return_value=httpx.Response(200, headers={"content-type": "image/jpeg"}, content=b"jpeg")
    )

    public_url = store_job_thumbnail(
        RAW_URL,
        owner_id=OWNER_ID,
        job_id=JOB_ID,
        settings=settings_with_storage_key(),
    )

    assert public_url == (
        "https://example.supabase.co/storage/v1/object/public/job-thumbnails/"
        f"users/{OWNER_ID}/jobs/{JOB_ID}/thumbnail.jpg"
    )
    assert bucket.uploads == [
        (
            f"users/{OWNER_ID}/jobs/{JOB_ID}/thumbnail.jpg",
            b"jpeg",
            {
                "cache-control": "31536000",
                "content-type": "image/jpeg",
                "upsert": "false",
            },
        )
    ]


@respx.mock
def test_store_job_thumbnail_skips_invalid_host(monkeypatch):
    bucket = FakeBucket()
    monkeypatch.setattr(
        "src.storage.thumbnails.create_client",
        lambda _url, _key: FakeSupabaseClient(bucket),
    )

    public_url = store_job_thumbnail(
        "https://example.com/thumb.jpg",
        owner_id=OWNER_ID,
        job_id=JOB_ID,
        settings=settings_with_storage_key(),
    )

    assert public_url is None
    assert bucket.uploads == []


@respx.mock
def test_store_job_thumbnail_skips_redirect_to_invalid_host(monkeypatch):
    bucket = FakeBucket()
    monkeypatch.setattr(
        "src.storage.thumbnails.create_client",
        lambda _url, _key: FakeSupabaseClient(bucket),
    )
    respx.get(RAW_URL).mock(
        return_value=httpx.Response(
            302,
            headers={"location": "https://example.com/not-instagram.jpg"},
        )
    )

    public_url = store_job_thumbnail(
        RAW_URL,
        owner_id=OWNER_ID,
        job_id=JOB_ID,
        settings=settings_with_storage_key(),
    )

    assert public_url is None
    assert bucket.uploads == []


@respx.mock
def test_store_job_thumbnail_skips_non_image_content(monkeypatch):
    bucket = FakeBucket()
    monkeypatch.setattr(
        "src.storage.thumbnails.create_client",
        lambda _url, _key: FakeSupabaseClient(bucket),
    )
    respx.get(RAW_URL).mock(
        return_value=httpx.Response(200, headers={"content-type": "text/html"}, content=b"nope")
    )

    public_url = store_job_thumbnail(
        RAW_URL,
        owner_id=OWNER_ID,
        job_id=JOB_ID,
        settings=settings_with_storage_key(),
    )

    assert public_url is None
    assert bucket.uploads == []


@respx.mock
def test_store_job_thumbnail_skips_oversized_image(monkeypatch):
    bucket = FakeBucket()
    monkeypatch.setattr(
        "src.storage.thumbnails.create_client",
        lambda _url, _key: FakeSupabaseClient(bucket),
    )
    respx.get(RAW_URL).mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "image/jpeg"},
            content=b"x" * (2 * 1024 * 1024 + 1),
        )
    )

    public_url = store_job_thumbnail(
        RAW_URL,
        owner_id=OWNER_ID,
        job_id=JOB_ID,
        settings=settings_with_storage_key(),
    )

    assert public_url is None
    assert bucket.uploads == []


@respx.mock
def test_store_job_thumbnail_skips_when_service_role_key_missing(monkeypatch):
    bucket = FakeBucket()
    monkeypatch.setattr(
        "src.storage.thumbnails.create_client",
        lambda _url, _key: FakeSupabaseClient(bucket),
    )

    public_url = store_job_thumbnail(
        RAW_URL,
        owner_id=OWNER_ID,
        job_id=JOB_ID,
        settings=Settings(auth=AuthConfig(supabase_project_url="https://example.supabase.co")),
    )

    assert public_url is None
    assert bucket.uploads == []
