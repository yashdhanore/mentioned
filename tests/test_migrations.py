from __future__ import annotations

from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "20260502_0002_owner_scope_result_tables.py"
)


def test_owner_scope_migration_covers_all_owner_scoped_tables() -> None:
    migration_sql = MIGRATION.read_text(encoding="utf-8")

    for table_name in ("jobs", "text_results", "artifacts", "job_stage_runs", "provider_calls", "saved_mentions"):
        assert f'"{table_name}"' in migration_sql

    assert "_add_owner_id(table_name)" in migration_sql
    assert "_create_owner_policy(table_name)" in migration_sql
    assert "create policy {table_name}_owner_policy" in migration_sql
    assert "current_setting('app.current_user_id', true)" in migration_sql
    assert "force row level security" in migration_sql
