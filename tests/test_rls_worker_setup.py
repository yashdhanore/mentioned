from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import Session, create_engine

from src.auth.dependencies import get_authenticated_session
from src.auth.schemas import Caller
from src.config import AuthConfig, DBConfig, Settings, validate_settings
from src.database import check_worker_database_role
from src.worker import resolve_worker_engine


class _Dialect:
    def __init__(self, name: str) -> None:
        self.name = name


class _RoleResult:
    def __init__(self, row: dict[str, object]) -> None:
        self.row = row

    def mappings(self):
        return self

    def one(self) -> dict[str, object]:
        return self.row


class _Connection:
    def __init__(self, row: dict[str, object]) -> None:
        self.row = row

    def __enter__(self):
        return self

    def __exit__(self, *_exc_info) -> None:
        return None

    def execute(self, _statement) -> _RoleResult:
        return _RoleResult(self.row)


class _Engine:
    def __init__(self, dialect_name: str, row: dict[str, object] | None = None) -> None:
        self.dialect = _Dialect(dialect_name)
        self.row = row or {
            "current_user": "mentioned_worker",
            "rolsuper": False,
            "rolbypassrls": False,
        }

    def connect(self) -> _Connection:
        return _Connection(self.row)


def test_authenticated_session_sets_rls_context() -> None:
    engine = create_engine("sqlite://")
    caller = Caller(subject_id="00000000-0000-4000-8000-000000000001", role="user")
    with Session(engine) as session:
        assert get_authenticated_session(caller, session) is session
        assert session.info["rls_user_id"] == caller.subject_id


def test_production_worker_requires_worker_database_url() -> None:
    settings = Settings(app_env="production")

    with pytest.raises(RuntimeError, match="WORKER_DATABASE_URL"):
        resolve_worker_engine(settings)


def test_worker_role_check_rejects_bypassrls() -> None:
    engine = _Engine(
        "postgresql",
        {
            "current_user": "mentioned_worker",
            "rolsuper": False,
            "rolbypassrls": True,
        },
    )

    with pytest.raises(RuntimeError, match="must not BYPASSRLS"):
        check_worker_database_role(engine)  # type: ignore[arg-type]


def test_worker_role_check_requires_postgres_when_requested() -> None:
    engine = _Engine("sqlite")

    check_worker_database_role(engine)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="worker database must be PostgreSQL"):
        check_worker_database_role(engine, require_postgres=True)  # type: ignore[arg-type]


def _production_settings(*, cors_allowed_origins: tuple[str, ...]) -> Settings:
    return Settings(
        app_env="production",
        docs_enabled=False,
        source_require_https=True,
        cors_allowed_origins=cors_allowed_origins,
        trusted_hosts=("mentioned-api.onrender.com",),
        db=DBConfig(
            database_url="postgresql://mentioned_api:password@example.supabase.co/postgres",
            auto_create_tables=False,
        ),
        auth=AuthConfig(
            auth_mode="supabase",
            supabase_project_url="https://example.supabase.co",
        ),
    )


def test_production_cors_allows_explicit_localhost_http_for_development() -> None:
    validate_settings(
        _production_settings(
            cors_allowed_origins=(
                "https://app.example.com",
                "http://localhost:8082",
                "http://127.0.0.1:8082",
            )
        )
    )


def test_production_cors_rejects_non_local_http_origins() -> None:
    with pytest.raises(RuntimeError, match="CORS_ALLOWED_ORIGINS"):
        validate_settings(
            _production_settings(cors_allowed_origins=("http://app.example.com",))
        )


def test_dedicated_worker_rls_migration_contains_role_scoped_grants_and_policies() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "20260505_0004_dedicated_worker_rls.py"
    ).read_text()

    assert "REVOKE ALL ON TABLE public.jobs, public.mentions FROM anon, authenticated" in migration
    assert "GRANT SELECT, INSERT ON TABLE public.jobs TO mentioned_api" in migration
    assert "GRANT SELECT, UPDATE ON TABLE public.jobs TO mentioned_worker" in migration
    assert "TO mentioned_api" in migration
    assert "TO mentioned_worker" in migration
    assert "current_setting('app.current_user_id', true)::uuid" in migration
    assert "USING (true)" in migration
    assert "WITH CHECK (true)" in migration


def test_book_migration_adds_books_table_and_nullable_mention_link() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "20260509_0005_books.py"
    ).read_text()

    assert 'op.create_table(\n        "books"' in migration
    assert 'sa.Column("book_id", UUID, nullable=True)' in migration
    assert 'op.create_foreign_key(\n        "mentions_book_id_fkey"' in migration
    assert "books_provider_volume_unique_idx" in migration
    assert "GRANT SELECT ON TABLE public.books TO mentioned_api" in migration
    assert "GRANT SELECT, INSERT, UPDATE ON TABLE public.books TO mentioned_worker" in migration


def test_extract_jobs_queue_migration_has_role_scoped_permissions() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "20260512_0006_extract_jobs_queue.py"
    ).read_text()

    assert "create extension if not exists pgmq" in migration
    assert "pgmq.create('extract_jobs')" in migration
    assert "GRANT USAGE ON SCHEMA pgmq TO mentioned_api, mentioned_worker" in migration
    assert "GRANT EXECUTE ON FUNCTION pgmq.send(text, jsonb, integer) TO mentioned_api" in migration
    assert (
        "GRANT EXECUTE ON FUNCTION pgmq.read_with_poll"
        "(text, integer, integer, integer, integer, jsonb)" in migration
    )
    assert "GRANT EXECUTE ON FUNCTION pgmq.archive(text, bigint) TO mentioned_worker" in migration
    assert "GRANT USAGE ON TYPE pgmq.message_record TO mentioned_worker" in migration
    assert "GRANT SELECT, INSERT ON TABLE pgmq.q_extract_jobs TO mentioned_api" in migration
    assert "GRANT SELECT, UPDATE, DELETE ON TABLE pgmq.q_extract_jobs TO mentioned_worker" in migration
    assert "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA pgmq TO mentioned_api, mentioned_worker" in migration
    assert "anon" not in migration
    assert "authenticated" not in migration


def test_extract_jobs_archive_grant_migration_allows_returning_archive_rows() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "20260513_0007_extract_jobs_archive_select_grant.py"
    ).read_text()

    assert "GRANT SELECT ON TABLE pgmq.a_extract_jobs TO mentioned_worker" in migration
    assert "REVOKE SELECT ON TABLE pgmq.a_extract_jobs FROM mentioned_worker" in migration


def test_job_events_migration_has_realtime_rls_and_role_scoped_permissions() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "20260513_0008_job_events.py"
    ).read_text()

    assert 'op.create_table(\n        "job_events"' in migration
    assert 'sa.UniqueConstraint("job_id", name="job_events_job_id_key")' in migration
    assert "ondelete=\"CASCADE\"" in migration
    assert "event_type in ('job_done', 'job_failed')" in migration
    assert "ALTER TABLE public.job_events ENABLE ROW LEVEL SECURITY" in migration
    assert "REVOKE ALL ON TABLE public.job_events FROM anon, authenticated" in migration
    assert "GRANT SELECT ON TABLE public.job_events TO authenticated" in migration
    assert "GRANT INSERT ON TABLE public.job_events TO mentioned_worker" in migration
    assert "CREATE POLICY job_events_owner_select ON public.job_events" in migration
    assert "USING (owner_id = auth.uid())" in migration
    assert "CREATE POLICY job_events_worker_insert ON public.job_events" in migration
    assert "WITH CHECK (true)" in migration
    assert "supabase_realtime" in migration
    assert "pg_publication" in migration
    assert "pg_publication_tables" in migration
