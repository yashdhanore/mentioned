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
        validate_settings(_production_settings(cors_allowed_origins=("http://app.example.com",)))


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations" / "versions"


def _initial_schema_migration() -> str:
    return (MIGRATIONS_DIR / "20260922_0018_initial_schema.py").read_text()


def test_squashed_migration_creates_books_table_with_role_scoped_grants() -> None:
    migration = _initial_schema_migration()

    assert 'op.create_table(\n        "books"' in migration
    assert "books_provider_volume_unique_idx" in migration
    assert "GRANT SELECT ON TABLE public.books TO mentioned_api" in migration
    assert "GRANT SELECT, INSERT, UPDATE ON TABLE public.books TO mentioned_worker" in migration
    # source_items carries the book link now that mentions is gone.
    assert 'sa.Column("book_id", UUID, sa.ForeignKey("books.id", ondelete="SET NULL")' in migration


def test_squashed_migration_creates_waitlist_with_rls_and_role_scoped_policy() -> None:
    migration = _initial_schema_migration()

    assert "CREATE TABLE public.waitlist_signups" in migration
    assert "CREATE UNIQUE INDEX waitlist_signups_email_lower_idx" in migration
    assert "ALTER TABLE public.waitlist_signups ENABLE ROW LEVEL SECURITY" in migration
    assert "REVOKE ALL ON TABLE public.waitlist_signups FROM anon, authenticated" in migration
    assert (
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.waitlist_signups TO mentioned_api"
        in migration
    )
    # The policy must be scoped to a role, not left unscoped: `FOR ALL USING (true)` with no
    # `TO <role>` applies to every role, including anon/authenticated as soon as anything
    # grants them table privileges.
    assert (
        "CREATE POLICY waitlist_signups_api_manage ON public.waitlist_signups\n"
        "          FOR ALL\n"
        "          TO mentioned_api" in migration
    )


def test_waitlist_supabase_migration_is_a_no_op() -> None:
    # Supabase applies its migrations before Alembic on a fresh database, so any DDL here
    # collides with the squashed Alembic revision that owns public.waitlist_signups.
    migration_path = next(
        (Path(__file__).resolve().parents[1] / "supabase" / "migrations").glob(
            "*_create_waitlist_signups.sql"
        )
    )
    statements = [
        line.strip()
        for line in migration_path.read_text().splitlines()
        if line.strip() and not line.strip().startswith("--")
    ]

    assert statements == ["select 1;"]


def test_squashed_migration_creates_push_tokens_with_owner_scoped_rls_and_queue() -> None:
    migration = _initial_schema_migration()

    assert 'op.create_table(\n        "push_tokens"' in migration
    assert "ALTER TABLE public.push_tokens ENABLE ROW LEVEL SECURITY" in migration
    assert "REVOKE ALL ON TABLE public.push_tokens FROM anon, authenticated" in migration
    assert (
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.push_tokens TO mentioned_api"
        in migration
    )
    assert "GRANT SELECT, UPDATE ON TABLE public.push_tokens TO mentioned_worker" in migration
    assert "CREATE POLICY push_tokens_api_owner_select ON public.push_tokens" in migration
    assert "CREATE POLICY push_tokens_api_owner_delete ON public.push_tokens" in migration
    assert "current_setting('app.current_user_id', true)::uuid" in migration
    assert "CREATE POLICY push_tokens_worker_select ON public.push_tokens" in migration
    assert "CREATE POLICY push_tokens_worker_update ON public.push_tokens" in migration
    assert "pgmq.create('push_notifications')" in migration
    assert (
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE pgmq.q_push_notifications TO mentioned_worker"
        in migration
    )
    assert (
        "GRANT SELECT, INSERT ON TABLE pgmq.a_push_notifications TO mentioned_worker" in migration
    )


def test_squashed_migration_creates_sources_and_saved_sources_with_owner_scoped_rls() -> None:
    migration = _initial_schema_migration()

    assert 'op.create_table(\n        "sources"' in migration
    assert 'op.create_table(\n        "source_items"' in migration
    assert 'op.create_table(\n        "saved_sources"' in migration
    assert 'sa.UniqueConstraint("source_key", name="sources_source_key_key")' in migration
    assert (
        'sa.UniqueConstraint("owner_id", "source_id", name="saved_sources_owner_source_key")'
        in migration
    )
    assert "GRANT SELECT, INSERT, UPDATE ON TABLE public.sources TO mentioned_api" in migration
    assert "GRANT SELECT ON TABLE public.source_items TO mentioned_api" in migration
    assert (
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.saved_sources TO mentioned_api"
        in migration
    )
    assert "GRANT DELETE ON TABLE public.source_items TO mentioned_worker" in migration
    assert "CREATE POLICY saved_sources_api_owner_all ON public.saved_sources" in migration
    assert "CREATE POLICY sources_api_insert ON public.sources" in migration
    assert "CREATE POLICY sources_api_retry_update ON public.sources" in migration
    assert "create extension if not exists pgmq" in migration
    assert "pgmq.create('extract_sources')" in migration
    assert (
        "GRANT EXECUTE ON FUNCTION pgmq.send(text, jsonb, integer) TO mentioned_api, "
        "mentioned_worker" in migration
    )
    assert (
        "GRANT EXECUTE ON FUNCTION pgmq.read_with_poll"
        "(text, integer, integer, integer, integer, jsonb)" in migration
    )
    assert "GRANT EXECUTE ON FUNCTION pgmq.archive(text, bigint) TO mentioned_worker" in migration
    assert "GRANT USAGE ON TYPE pgmq.message_record TO mentioned_worker" in migration
    assert "GRANT SELECT, INSERT ON TABLE pgmq.q_extract_sources TO mentioned_api" in migration
    assert (
        "GRANT SELECT, UPDATE, DELETE ON TABLE pgmq.q_extract_sources TO mentioned_worker"
        in migration
    )
    assert "GRANT SELECT, INSERT ON TABLE pgmq.a_extract_sources TO mentioned_worker" in migration
    # The legacy jobs/mentions/job_events tables and extract_jobs queue were
    # created and dropped within the old chain; the squash never recreates them.
    assert "public.jobs" not in migration
    assert "public.mentions" not in migration
    assert "public.job_events" not in migration
    assert "pgmq.create('extract_jobs')" not in migration
