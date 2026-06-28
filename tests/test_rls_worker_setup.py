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


def test_waitlist_supabase_migration_has_rls_and_role_scoped_permissions() -> None:
    migration_path = next(
        (
            Path(__file__).resolve().parents[1] / "supabase" / "migrations"
        ).glob("*_create_waitlist_signups.sql")
    )
    migration = migration_path.read_text()

    assert "create table if not exists public.waitlist_signups" in migration
    assert "create unique index if not exists waitlist_signups_email_lower_idx" in migration
    assert "alter table public.waitlist_signups enable row level security" in migration
    assert "revoke all on table public.waitlist_signups from anon, authenticated" in migration
    assert "create policy waitlist_signups_app_manage" in migration
    assert "grant select, insert, update on table public.waitlist_signups to mentioned_api" in migration


def test_push_notifications_migration_has_private_tokens_and_worker_queue() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "20260514_0009_push_notifications.py"
    ).read_text()

    assert 'op.create_table(\n        "push_tokens"' in migration
    assert "ALTER TABLE public.push_tokens ENABLE ROW LEVEL SECURITY" in migration
    assert "REVOKE ALL ON TABLE public.push_tokens FROM anon, authenticated" in migration
    assert "GRANT SELECT, INSERT, UPDATE ON TABLE public.push_tokens TO mentioned_api" in migration
    assert "GRANT SELECT, UPDATE ON TABLE public.push_tokens TO mentioned_worker" in migration
    assert "CREATE POLICY push_tokens_api_owner_select ON public.push_tokens" in migration
    assert "current_setting('app.current_user_id', true)::uuid" in migration
    assert "CREATE POLICY push_tokens_worker_select ON public.push_tokens" in migration
    assert "CREATE POLICY push_tokens_worker_update ON public.push_tokens" in migration
    assert "pgmq.create('push_notifications')" in migration
    assert "GRANT EXECUTE ON FUNCTION pgmq.send(text, jsonb, integer) TO mentioned_worker" in migration
    assert "GRANT EXECUTE ON FUNCTION pgmq.read(text, integer, integer, jsonb) TO mentioned_worker" in migration
    assert "GRANT EXECUTE ON FUNCTION pgmq.archive(text, bigint) TO mentioned_worker" in migration
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE pgmq.q_push_notifications TO mentioned_worker" in migration
    assert "GRANT SELECT, INSERT ON TABLE pgmq.a_push_notifications TO mentioned_worker" in migration


def test_delete_saved_posts_migration_grants_api_delete_under_rls() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "20260606_0012_delete_saved_posts.py"
    ).read_text()

    assert "GRANT DELETE ON TABLE public.jobs, public.mentions TO mentioned_api" in migration
    assert "GRANT SELECT, DELETE ON TABLE public.job_events TO mentioned_api" in migration
    assert "CREATE POLICY jobs_api_owner_delete ON public.jobs" in migration
    assert "CREATE POLICY mentions_api_owner_delete ON public.mentions" in migration
    assert "CREATE POLICY job_events_api_owner_select ON public.job_events" in migration
    assert "CREATE POLICY job_events_api_owner_delete ON public.job_events" in migration
    assert "current_setting('app.current_user_id', true)::uuid" in migration


def test_sources_migration_has_cache_and_owner_scoped_permissions() -> None:
    migration = (
        Path("migrations/versions/20260622_0014_sources_saved_sources.py")
        .read_text()
    )

    assert 'op.create_table(\n        "sources"' in migration
    assert 'op.create_table(\n        "source_items"' in migration
    assert 'op.create_table(\n        "saved_sources"' in migration
    assert 'sa.UniqueConstraint("source_key", name="sources_source_key_key")' in migration
    assert 'sa.UniqueConstraint("owner_id", "source_id", name="saved_sources_owner_source_key")' in migration
    assert "GRANT SELECT, INSERT, UPDATE ON TABLE public.sources TO mentioned_api" in migration
    assert "GRANT SELECT ON TABLE public.source_items TO mentioned_api" in migration
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.saved_sources TO mentioned_api" in migration
    assert "CREATE POLICY saved_sources_api_owner_all ON public.saved_sources" in migration
    assert "CREATE POLICY sources_api_insert ON public.sources" in migration
    assert "CREATE POLICY sources_api_retry_update ON public.sources" in migration
    assert "create extension if not exists pgmq" in migration
    assert "pgmq.create('extract_sources')" in migration
    assert "GRANT EXECUTE ON FUNCTION pgmq.send(text, jsonb, integer) TO mentioned_api" in migration
    assert (
        "GRANT EXECUTE ON FUNCTION pgmq.read_with_poll"
        "(text, integer, integer, integer, integer, jsonb)" in migration
    )
    assert "GRANT EXECUTE ON FUNCTION pgmq.archive(text, bigint) TO mentioned_worker" in migration
    assert "GRANT USAGE ON TYPE pgmq.message_record TO mentioned_worker" in migration
    assert "GRANT SELECT, INSERT ON TABLE pgmq.q_extract_sources TO mentioned_api" in migration
    assert "GRANT SELECT, UPDATE, DELETE ON TABLE pgmq.q_extract_sources TO mentioned_worker" in migration
    assert "GRANT SELECT, INSERT ON TABLE pgmq.a_extract_sources TO mentioned_worker" in migration
