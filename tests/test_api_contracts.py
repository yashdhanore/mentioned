from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import Header
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import db
from app.auth import Caller
from app.config import Settings
from app.db import get_session
from app.deps import get_current_caller
from app.main import app
from app.models import Job, SavedMention, utc_now


@pytest.fixture()
def api_engine() -> Engine:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture()
def client(api_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    def override_session() -> Iterator[Session]:
        with Session(api_engine) as session:
            yield session

    def override_caller(authorization: str | None = Header(default=None)) -> Caller:
        if authorization and authorization.casefold().startswith("bearer dev:"):
            return Caller(subject_id=authorization.split("dev:", 1)[1], role="user")
        return Caller(subject_id="00000000-0000-4000-8000-000000000001", role="user")

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_caller] = override_caller
    monkeypatch.setattr(db, "settings", Settings(database_url="sqlite://"))
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def _settings(**overrides: object) -> Settings:
    values = {
        "database_url": "sqlite://",
        "max_job_create_burst_per_minute": 100,
        "max_jobs_created_per_day": 100,
        "max_active_jobs_per_user": 100,
    }
    values.update(overrides)
    return Settings(**values)


def _auth(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer dev:{user_id}"}


def _create_job(
    client: TestClient,
    shortcode: str,
    *,
    user_id: str = "00000000-0000-4000-8000-000000000111",
    idempotency_key: str | None = None,
) -> dict:
    payload = {"url": f"https://www.instagram.com/reel/{shortcode}/"}
    if idempotency_key is not None:
        payload["idempotency_key"] = idempotency_key
    response = client.post("/v1/jobs", json=payload, headers=_auth(user_id))
    assert response.status_code == 202
    return response.json()


def _mark_job_terminal(api_engine: Engine, job_id: str, status: str = "succeeded") -> None:
    with Session(api_engine) as session:
        job = session.get(Job, job_id)
        assert job is not None
        now = utc_now()
        job.status = status
        job.current_stage = "completed"
        job.progress = 1.0
        job.finished_at = now
        job.updated_at = now
        session.add(job)
        session.commit()


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
    monkeypatch.setattr(db, "settings", Settings(database_url="sqlite://"))
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


def test_mentions_endpoint_returns_minimal_public_shape(client: TestClient, api_engine: Engine) -> None:
    user_id = "00000000-0000-4000-8000-000000000111"
    created = _create_job(client, "mention-shape", user_id=user_id)
    with Session(api_engine) as session:
        session.add(
            SavedMention(
                owner_id=user_id,
                source_job_id=created["job_id"],
                category="book",
                display_label="The Visible Book",
                display_author_or_creator="A. Writer",
                display_description="A clean public description.",
                extracted_label="The Visible Book",
                extracted_author_or_creator="A. Writer",
                source_url="https://www.instagram.com/reel/mention-shape/",
                source_platform="instagram",
                source_context_snippet="Short clean context",
                evidence_text="raw evidence should stay private",
                evidence_json={"source": "openai"},
                confidence=0.91,
                candidate_fingerprint="shape-test",
                save_state="active",
                review_status="unreviewed",
            )
        )
        session.commit()

    response = client.get("/v1/mentions", headers=_auth(user_id))

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["label"] == "The Visible Book"
    assert item["author_or_creator"] == "A. Writer"
    assert item["description"] == "A clean public description."
    assert item["source_context_snippet"] == "Short clean context"
    assert item["confidence"] == 0.91
    assert "display_label" not in item
    assert "extracted_label" not in item
    assert "evidence" not in item
    assert "evidence_text" not in item
    assert "save_state" not in item
    assert "review_status" not in item


def test_create_job_burst_limit_returns_public_rate_limited(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.job_coordinator.get_settings",
        lambda: _settings(max_job_create_burst_per_minute=1),
    )
    _create_job(client, "burst1")

    response = client.post(
        "/v1/jobs",
        json={"url": "https://www.instagram.com/reel/burst2/"},
        headers=_auth("00000000-0000-4000-8000-000000000111"),
    )

    assert response.status_code == 429
    assert response.json()["detail"]["error_code"] == "rate_limited"


def test_create_job_daily_limit_returns_public_quota_exceeded(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.job_coordinator.get_settings",
        lambda: _settings(max_jobs_created_per_day=1),
    )
    _create_job(client, "daily1")

    response = client.post(
        "/v1/jobs",
        json={"url": "https://www.instagram.com/reel/daily2/"},
        headers=_auth("00000000-0000-4000-8000-000000000111"),
    )

    assert response.status_code == 429
    assert response.json()["detail"]["error_code"] == "quota_exceeded"


def test_create_job_active_limit_returns_public_quota_exceeded(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.job_coordinator.get_settings",
        lambda: _settings(max_active_jobs_per_user=1),
    )
    _create_job(client, "active1")

    response = client.post(
        "/v1/jobs",
        json={"url": "https://www.instagram.com/reel/active2/"},
        headers=_auth("00000000-0000-4000-8000-000000000111"),
    )

    assert response.status_code == 429
    assert response.json()["detail"]["error_code"] == "quota_exceeded"


def test_create_job_quotas_are_owner_scoped(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.job_coordinator.get_settings",
        lambda: _settings(max_job_create_burst_per_minute=1),
    )
    _create_job(client, "owner1", user_id="00000000-0000-4000-8000-000000000111")

    response = client.post(
        "/v1/jobs",
        json={"url": "https://www.instagram.com/reel/owner2/"},
        headers=_auth("00000000-0000-4000-8000-000000000222"),
    )

    assert response.status_code == 202


def test_terminal_jobs_do_not_count_against_active_quota(
    client: TestClient,
    api_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.job_coordinator.get_settings",
        lambda: _settings(max_active_jobs_per_user=1),
    )
    created = _create_job(client, "terminal1")
    _mark_job_terminal(api_engine, created["job_id"])

    response = client.post(
        "/v1/jobs",
        json={"url": "https://www.instagram.com/reel/terminal2/"},
        headers=_auth("00000000-0000-4000-8000-000000000111"),
    )

    assert response.status_code == 202


def test_idempotent_replay_returns_existing_job_without_consuming_quota(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.job_coordinator.get_settings",
        lambda: _settings(
            max_job_create_burst_per_minute=1,
            max_jobs_created_per_day=1,
            max_active_jobs_per_user=1,
        ),
    )
    first = _create_job(client, "idem1", idempotency_key="idem-0001")

    replay_response = client.post(
        "/v1/jobs",
        json={"url": "https://www.instagram.com/reel/idem1/", "idempotency_key": "idem-0001"},
        headers=_auth("00000000-0000-4000-8000-000000000111"),
    )
    conflict_response = client.post(
        "/v1/jobs",
        json={"url": "https://www.instagram.com/reel/idem2/", "idempotency_key": "idem-0001"},
        headers=_auth("00000000-0000-4000-8000-000000000111"),
    )

    assert replay_response.status_code == 202
    assert replay_response.json()["job_id"] == first["job_id"]
    assert conflict_response.status_code == 409
    assert conflict_response.json()["detail"]["error_code"] == "idempotency_conflict"


def test_rerun_terminal_job_obeys_active_quota_without_counting_itself(
    client: TestClient,
    api_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_box = {
        "settings": _settings(max_active_jobs_per_user=100),
    }
    monkeypatch.setattr("app.services.job_coordinator.get_settings", lambda: settings_box["settings"])
    terminal = _create_job(client, "rerun1")
    _mark_job_terminal(api_engine, terminal["job_id"])

    settings_box["settings"] = _settings(max_active_jobs_per_user=1)
    allowed_response = client.post(
        f"/v1/jobs/{terminal['job_id']}/rerun",
        headers=_auth("00000000-0000-4000-8000-000000000111"),
    )
    assert allowed_response.status_code == 200
    assert allowed_response.json()["status"] == "queued"

    _mark_job_terminal(api_engine, terminal["job_id"])
    _create_job(client, "rerun2")

    blocked_response = client.post(
        f"/v1/jobs/{terminal['job_id']}/rerun",
        headers=_auth("00000000-0000-4000-8000-000000000111"),
    )

    assert blocked_response.status_code == 429
    assert blocked_response.json()["detail"]["error_code"] == "quota_exceeded"
