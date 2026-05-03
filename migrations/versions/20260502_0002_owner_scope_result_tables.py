"""add owner scope to result tables

Revision ID: 20260502_0002
Revises: 20260430_0001
Create Date: 2026-05-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260502_0002"
down_revision = "20260430_0001"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
OWNER_POLICY_EXPR = "owner_id = nullif(current_setting('app.current_user_id', true), '')::uuid"
OWNER_TABLES = ("jobs", "text_results", "artifacts", "job_stage_runs", "provider_calls", "saved_mentions")


def _add_owner_id(table_name: str) -> None:
    op.add_column(table_name, sa.Column("owner_id", UUID, nullable=True))
    op.execute(
        sa.text(
            f"""
            update {table_name}
            set owner_id = jobs.owner_id
            from jobs
            where {table_name}.job_id = jobs.id
            """
        )
    )
    op.alter_column(table_name, "owner_id", existing_type=UUID, nullable=False)


def _drop_owner_policy(table_name: str) -> None:
    op.execute(f"drop policy if exists {table_name}_owner_policy on {table_name}")


def _create_owner_policy(table_name: str) -> None:
    op.execute(f"alter table {table_name} enable row level security")
    op.execute(f"alter table {table_name} force row level security")
    op.execute(
        f"""
        create policy {table_name}_owner_policy on {table_name}
          for all
          using ({OWNER_POLICY_EXPR})
          with check ({OWNER_POLICY_EXPR})
        """
    )


def _restore_supabase_owner_policy(table_name: str) -> None:
    op.execute(f"alter table {table_name} no force row level security")
    op.execute(
        f"""
        create policy {table_name}_owner_policy on {table_name}
          for all
          using (owner_id = (select auth.uid()))
          with check (owner_id = (select auth.uid()))
        """
    )


def upgrade() -> None:
    for table_name in ("text_results", "artifacts", "job_stage_runs", "provider_calls"):
        _add_owner_id(table_name)

    op.create_index("text_results_owner_job_idx", "text_results", ["owner_id", "job_id"])
    op.create_index(
        "artifacts_owner_job_kind_created_idx",
        "artifacts",
        ["owner_id", "job_id", "kind", "created_at", "id"],
    )
    op.create_index(
        "job_stage_runs_owner_job_created_idx",
        "job_stage_runs",
        ["owner_id", "job_id", "created_at", "id"],
    )
    op.create_index(
        "provider_calls_owner_job_created_idx",
        "provider_calls",
        ["owner_id", "job_id", "created_at", "id"],
    )

    for table_name in ("jobs", "saved_mentions"):
        _drop_owner_policy(table_name)
    for table_name in OWNER_TABLES:
        _create_owner_policy(table_name)


def downgrade() -> None:
    for table_name in OWNER_TABLES:
        _drop_owner_policy(table_name)

    for table_name in ("text_results", "artifacts", "job_stage_runs", "provider_calls"):
        op.execute(f"alter table {table_name} no force row level security")
        op.execute(f"alter table {table_name} disable row level security")

    for table_name in ("jobs", "saved_mentions"):
        _restore_supabase_owner_policy(table_name)

    op.drop_index("provider_calls_owner_job_created_idx", table_name="provider_calls")
    op.drop_index("job_stage_runs_owner_job_created_idx", table_name="job_stage_runs")
    op.drop_index("artifacts_owner_job_kind_created_idx", table_name="artifacts")
    op.drop_index("text_results_owner_job_idx", table_name="text_results")

    for table_name in ("provider_calls", "job_stage_runs", "artifacts", "text_results"):
        op.drop_column(table_name, "owner_id")
