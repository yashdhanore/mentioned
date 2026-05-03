from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import Header
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.auth import Caller
from app.config import Settings
from app.db import get_session
from app.deps import get_current_caller
from app.main import app


@pytest.fixture()
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    def override_caller(authorization: str | None = Header(default=None)) -> Caller:
        if authorization and authorization.casefold().startswith("bearer dev:"):
            return Caller(subject_id=authorization.split("dev:", 1)[1], role="user")
        return Caller(subject_id="00000000-0000-4000-8000-000000000001", role="user")

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_caller] = override_caller
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def supabase_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    monkeypatch.setattr(
        "app.auth.get_settings",
        lambda: Settings(
            auth_mode="supabase",
            supabase_project_url="https://example.supabase.co",
            supabase_jwt_secret="secret",
        ),
    )
    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_supabase_auth_returns_401_for_missing_or_invalid_tokens(supabase_client: TestClient) -> None:
    missing_response = supabase_client.get("/v1/jobs")
    assert missing_response.status_code == 401

    invalid_response = supabase_client.get("/v1/jobs", headers={"Authorization": "Bearer invalid-token"})
    assert invalid_response.status_code == 401


def test_create_job_rejects_unknown_fields_and_bad_hosts(client: TestClient) -> None:
    unknown_field_response = client.post(
        "/v1/jobs",
        json={"url": "https://www.instagram.com/reel/abc/", "extra": True},
        headers={"Authorization": "Bearer dev:00000000-0000-4000-8000-000000000111"},
    )
    assert unknown_field_response.status_code == 422
    assert unknown_field_response.json()["detail"]["error_code"] == "validation_error"
    assert unknown_field_response.json()["detail"]["message"] == "The request is not valid."

    invalid_query_response = client.get(
        "/v1/jobs?limit=0",
        headers={"Authorization": "Bearer dev:00000000-0000-4000-8000-000000000111"},
    )
    assert invalid_query_response.status_code == 422
    assert invalid_query_response.json()["detail"]["error_code"] == "validation_error"

    spoofed_host_response = client.post(
        "/v1/jobs",
        json={"url": "https://instagram.com.evil.example/reel/abc/"},
        headers={"Authorization": "Bearer dev:00000000-0000-4000-8000-000000000111"},
    )
    assert spoofed_host_response.status_code == 422
    assert spoofed_host_response.json()["detail"]["error_code"] == "unsupported_source_kind"


def test_user_cannot_read_another_users_job(client: TestClient) -> None:
    create_response = client.post(
        "/v1/jobs",
        json={"url": "https://www.instagram.com/reel/abc/", "idempotency_key": "idem-123456"},
        headers={"Authorization": "Bearer dev:00000000-0000-4000-8000-000000000111"},
    )
    assert create_response.status_code == 202
    job_id = create_response.json()["job_id"]

    forbidden_response = client.get(
        f"/v1/jobs/{job_id}",
        headers={"Authorization": "Bearer dev:00000000-0000-4000-8000-000000000222"},
    )
    assert forbidden_response.status_code == 404
    forbidden_result_response = client.get(
        f"/v1/jobs/{job_id}/result",
        headers={"Authorization": "Bearer dev:00000000-0000-4000-8000-000000000222"},
    )
    assert forbidden_result_response.status_code == 404
    forbidden_rerun_response = client.post(
        f"/v1/jobs/{job_id}/rerun",
        headers={"Authorization": "Bearer dev:00000000-0000-4000-8000-000000000222"},
    )
    assert forbidden_rerun_response.status_code == 404
    forbidden_cancel_response = client.post(
        f"/v1/jobs/{job_id}/cancel",
        headers={"Authorization": "Bearer dev:00000000-0000-4000-8000-000000000222"},
    )
    assert forbidden_cancel_response.status_code == 404

    list_response = client.get(
        "/v1/jobs",
        headers={"Authorization": "Bearer dev:00000000-0000-4000-8000-000000000111"},
    )
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["job_id"] == job_id
    other_list_response = client.get(
        "/v1/jobs",
        headers={"Authorization": "Bearer dev:00000000-0000-4000-8000-000000000222"},
    )
    assert other_list_response.status_code == 200
    assert other_list_response.json()["items"] == []
