from __future__ import annotations

"""
Run the real Postgres API-role RLS proof with:

    POSTGRES_TEST_DATABASE_URL=postgresql://admin-or-owner-url \
    POSTGRES_TEST_API_DATABASE_URL=postgresql://mentioned_api-url \
    python -m pytest tests/test_postgres_rls_role_enforcement.py
"""

from collections.abc import Iterator
import os
from uuid import uuid4

from fastapi import Header
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, select

from app import db
from app.auth import Caller
from app.config import Settings
from app.db import get_session, normalize_database_url, set_rls_user_context
from app.deps import get_current_caller
from app.main import app
from app.models import Job


POSTGRES_TEST_DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
POSTGRES_TEST_API_DATABASE_URL = os.getenv("POSTGRES_TEST_API_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_DATABASE_URL or not POSTGRES_TEST_API_DATABASE_URL,
    reason="POSTGRES_TEST_DATABASE_URL and POSTGRES_TEST_API_DATABASE_URL are required for the real API-role RLS proof.",
)

OWNER_TABLES = ("jobs", "text_results", "artifacts", "job_stage_runs", "provider_calls", "saved_mentions")
OWNER_POLICY_EXPR = "owner_id = nullif(current_setting('app.current_user_id', true), '')::uuid"
USER_A = "00000000-0000-4000-8000-000000000111"
USER_B = "00000000-0000-4000-8000-000000000222"


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _engine_with_search_path(database_url: str, schema_name: str) -> Engine:
    engine = create_engine(normalize_database_url(database_url), pool_pre_ping=True)

    @event.listens_for(engine, "connect")
    def _set_search_path(dbapi_connection, _connection_record) -> None:
        with dbapi_connection.cursor() as cursor:
            cursor.execute(f"set search_path to {_quote_identifier(schema_name)}")

    return engine


def _api_role_name(database_url: str) -> str:
    probe_engine = create_engine(normalize_database_url(database_url), pool_pre_ping=True)
    try:
        with probe_engine.connect() as connection:
            return connection.execute(text("select current_user")).scalar_one()
    finally:
        probe_engine.dispose()


def _create_owner_policies(connection) -> None:
    for table_name in OWNER_TABLES:
        connection.execute(text(f"alter table {table_name} enable row level security"))
        connection.execute(text(f"alter table {table_name} force row level security"))
        connection.execute(text(f"drop policy if exists {table_name}_owner_policy on {table_name}"))
        connection.execute(
            text(
                f"""
                create policy {table_name}_owner_policy on {table_name}
                  for all
                  using ({OWNER_POLICY_EXPR})
                  with check ({OWNER_POLICY_EXPR})
                """
            )
        )


@pytest.fixture()
def postgres_api_engine() -> Iterator[Engine]:
    assert POSTGRES_TEST_DATABASE_URL is not None
    assert POSTGRES_TEST_API_DATABASE_URL is not None
    schema_name = f"test_api_rls_{uuid4().hex}"
    api_role = _api_role_name(POSTGRES_TEST_API_DATABASE_URL)
    admin_engine = create_engine(normalize_database_url(POSTGRES_TEST_DATABASE_URL), pool_pre_ping=True)

    with admin_engine.begin() as connection:
        connection.execute(text(f"create schema {_quote_identifier(schema_name)}"))

    schema_engine = _engine_with_search_path(POSTGRES_TEST_DATABASE_URL, schema_name)
    api_engine = _engine_with_search_path(POSTGRES_TEST_API_DATABASE_URL, schema_name)
    try:
        SQLModel.metadata.create_all(schema_engine)
        with schema_engine.begin() as connection:
            connection.execute(
                text(f"grant usage on schema {_quote_identifier(schema_name)} to {_quote_identifier(api_role)}")
            )
            connection.execute(
                text(
                    "grant select, insert, update, delete "
                    f"on all tables in schema {_quote_identifier(schema_name)} "
                    f"to {_quote_identifier(api_role)}"
                )
            )
            connection.execute(
                text(
                    """
                    insert into jobs (id, owner_id, source_url, source_kind)
                    values
                      (:job_a, :user_a, 'https://www.instagram.com/reel/user-a/', 'instagram_reel'),
                      (:job_b, :user_b, 'https://www.instagram.com/reel/user-b/', 'instagram_reel')
                    """
                ),
                {
                    "job_a": str(uuid4()),
                    "job_b": str(uuid4()),
                    "user_a": USER_A,
                    "user_b": USER_B,
                },
            )
            _create_owner_policies(connection)
        yield api_engine
    finally:
        api_engine.dispose()
        schema_engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f"drop schema if exists {_quote_identifier(schema_name)} cascade"))
        admin_engine.dispose()


def test_api_role_is_non_superuser_and_does_not_bypass_rls(postgres_api_engine: Engine) -> None:
    with postgres_api_engine.connect() as connection:
        row = connection.execute(
            text(
                """
                select rolsuper, rolbypassrls
                from pg_roles
                where rolname = current_user
                """
            )
        ).mappings().one()

    assert row["rolsuper"] is False
    assert row["rolbypassrls"] is False


def test_api_role_rls_filters_jobs_by_current_user(postgres_api_engine: Engine) -> None:
    with Session(postgres_api_engine) as session:
        assert session.exec(select(Job)).all() == []

    with Session(postgres_api_engine) as session:
        set_rls_user_context(session, USER_A)
        user_a_rows = session.exec(select(Job.owner_id).order_by(Job.owner_id)).all()

    with Session(postgres_api_engine) as session:
        set_rls_user_context(session, USER_B)
        user_b_rows = session.exec(select(Job.owner_id).order_by(Job.owner_id)).all()

    assert user_a_rows == [USER_A]
    assert user_b_rows == [USER_B]


def test_fastapi_user_flow_uses_api_role_with_rls(postgres_api_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    def override_session() -> Iterator[Session]:
        with Session(postgres_api_engine) as session:
            yield session

    def override_caller(authorization: str | None = Header(default=None)) -> Caller:
        if authorization and authorization.casefold().startswith("bearer dev:"):
            return Caller(subject_id=authorization.split("dev:", 1)[1], role="user")
        return Caller(subject_id=USER_A, role="user")

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_caller] = override_caller
    monkeypatch.setattr(db, "settings", Settings(database_url="sqlite://"))
    try:
        with TestClient(app) as client:
            create_response = client.post(
                "/v1/jobs",
                json={"url": "https://www.instagram.com/reel/api-role/"},
                headers={"Authorization": f"Bearer dev:{USER_A}"},
            )
            assert create_response.status_code == 202
            job_id = create_response.json()["job_id"]

            user_a_list_response = client.get("/v1/jobs", headers={"Authorization": f"Bearer dev:{USER_A}"})
            assert user_a_list_response.status_code == 200
            assert any(item["job_id"] == job_id for item in user_a_list_response.json()["items"])

            user_b_get_response = client.get(f"/v1/jobs/{job_id}", headers={"Authorization": f"Bearer dev:{USER_B}"})
            assert user_b_get_response.status_code == 404

            user_b_list_response = client.get("/v1/jobs", headers={"Authorization": f"Bearer dev:{USER_B}"})
            assert user_b_list_response.status_code == 200
            assert all(item["job_id"] != job_id for item in user_b_list_response.json()["items"])
    finally:
        app.dependency_overrides.clear()
