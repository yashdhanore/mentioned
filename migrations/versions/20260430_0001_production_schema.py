"""create production job and library schema

Revision ID: 20260430_0001
Revises:
Create Date: 2026-04-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260430_0001"
down_revision = None
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("current_stage", sa.Text(), nullable=True),
        sa.Column("progress", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("locked_by", sa.Text(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("internal_error", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status in ('queued', 'running', 'succeeded', 'partial', 'failed', 'canceled', 'expired')",
            name="jobs_status_check",
        ),
        sa.CheckConstraint("progress >= 0 and progress <= 1", name="jobs_progress_check"),
        sa.CheckConstraint("attempt_count >= 0", name="jobs_attempt_count_check"),
        sa.CheckConstraint("max_attempts >= 1", name="jobs_max_attempts_check"),
    )
    op.create_index("jobs_owner_created_id_idx", "jobs", ["owner_id", sa.text("created_at desc"), sa.text("id desc")])
    op.create_index(
        "jobs_queued_claim_idx",
        "jobs",
        ["status", "next_run_at", sa.text("priority desc"), "created_at", "id"],
        postgresql_where=sa.text("status = 'queued'"),
    )
    op.create_index(
        "jobs_running_heartbeat_idx",
        "jobs",
        ["status", "heartbeat_at"],
        postgresql_where=sa.text("status = 'running'"),
    )
    op.create_index(
        "jobs_owner_idempotency_uidx",
        "jobs",
        ["owner_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key is not null"),
    )

    op.create_table(
        "job_stage_runs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("attempt_number >= 1", name="job_stage_runs_attempt_number_check"),
        sa.CheckConstraint("duration_ms >= 0", name="job_stage_runs_duration_ms_check"),
    )
    op.create_index("job_stage_runs_job_created_idx", "job_stage_runs", ["job_id", "created_at", "id"])

    op.create_table(
        "artifacts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("storage_backend", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=True),
        sa.Column("byte_size", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("attempt_number >= 1", name="artifacts_attempt_number_check"),
        sa.CheckConstraint("byte_size is null or byte_size >= 0", name="artifacts_byte_size_check"),
    )
    op.create_index("artifacts_job_kind_created_idx", "artifacts", ["job_id", "kind", "created_at", "id"])

    op.create_table(
        "text_results",
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("caption_text", sa.Text(), nullable=True),
        sa.Column("spoken_text", sa.Text(), nullable=True),
        sa.Column("visual_text", sa.Text(), nullable=True),
        sa.Column("image_text", sa.Text(), nullable=True),
        sa.Column("merged_text", sa.Text(), nullable=False),
        sa.Column("warnings", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("debug", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("attempt_number >= 1", name="text_results_attempt_number_check"),
    )

    op.create_table(
        "provider_calls",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("input_token_count", sa.Integer(), nullable=True),
        sa.Column("output_token_count", sa.Integer(), nullable=True),
        sa.Column("input_image_count", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("attempt_number >= 1", name="provider_calls_attempt_number_check"),
        sa.CheckConstraint("duration_ms >= 0", name="provider_calls_duration_ms_check"),
    )
    op.create_index("provider_calls_job_created_idx", "provider_calls", ["job_id", "created_at", "id"])

    op.create_table(
        "saved_mentions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("source_job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_artifact_id", UUID, sa.ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("display_label", sa.Text(), nullable=False),
        sa.Column("display_author_or_creator", sa.Text(), nullable=True),
        sa.Column("display_description", sa.Text(), nullable=True),
        sa.Column("extracted_label", sa.Text(), nullable=False),
        sa.Column("extracted_author_or_creator", sa.Text(), nullable=True),
        sa.Column("extracted_description", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_platform", sa.Text(), nullable=False, server_default="instagram"),
        sa.Column("source_creator", sa.Text(), nullable=True),
        sa.Column("source_context_snippet", sa.Text(), nullable=True),
        sa.Column("evidence_text", sa.Text(), nullable=True),
        sa.Column("evidence", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("candidate_fingerprint", sa.Text(), nullable=False),
        sa.Column("save_state", sa.Text(), nullable=False, server_default="active"),
        sa.Column("review_status", sa.Text(), nullable=False, server_default="unreviewed"),
        sa.Column("created_by", sa.Text(), nullable=False, server_default="extraction"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "category in ('book', 'product', 'place', 'newsletter', 'person', 'unknown')",
            name="saved_mentions_category_check",
        ),
        sa.CheckConstraint("save_state in ('active', 'deleted')", name="saved_mentions_save_state_check"),
        sa.CheckConstraint(
            "review_status in ('unreviewed', 'reviewed')",
            name="saved_mentions_review_status_check",
        ),
        sa.CheckConstraint(
            "confidence is null or (confidence >= 0 and confidence <= 1)",
            name="saved_mentions_confidence_check",
        ),
        sa.UniqueConstraint("source_job_id", "candidate_fingerprint", name="saved_mentions_source_candidate_uidx"),
    )
    op.create_index(
        "saved_mentions_owner_created_id_idx",
        "saved_mentions",
        ["owner_id", sa.text("created_at desc"), sa.text("id desc")],
    )
    op.create_index(
        "saved_mentions_owner_category_created_idx",
        "saved_mentions",
        ["owner_id", "category", sa.text("created_at desc"), sa.text("id desc")],
    )
    op.create_index(
        "saved_mentions_owner_creator_created_idx",
        "saved_mentions",
        ["owner_id", "source_creator", sa.text("created_at desc"), sa.text("id desc")],
        postgresql_where=sa.text("source_creator is not null"),
    )
    op.create_index("saved_mentions_source_job_idx", "saved_mentions", ["source_job_id"])
    op.create_index(
        "saved_mentions_search_idx",
        "saved_mentions",
        [
            sa.text(
                "to_tsvector('simple', "
                "coalesce(display_label, '') || ' ' || "
                "coalesce(display_author_or_creator, '') || ' ' || "
                "coalesce(display_description, ''))"
            )
        ],
        postgresql_using="gin",
    )

    for table_name in ("jobs", "saved_mentions"):
        op.execute(f"alter table {table_name} enable row level security")
    op.execute(
        """
        create policy jobs_owner_policy on jobs
          for all
          using (owner_id = (select auth.uid()))
          with check (owner_id = (select auth.uid()))
        """
    )
    op.execute(
        """
        create policy saved_mentions_owner_policy on saved_mentions
          for all
          using (owner_id = (select auth.uid()))
          with check (owner_id = (select auth.uid()))
        """
    )


def downgrade() -> None:
    op.execute("drop policy if exists saved_mentions_owner_policy on saved_mentions")
    op.execute("drop policy if exists jobs_owner_policy on jobs")
    op.drop_index("saved_mentions_search_idx", table_name="saved_mentions")
    op.drop_index("saved_mentions_source_job_idx", table_name="saved_mentions")
    op.drop_index("saved_mentions_owner_creator_created_idx", table_name="saved_mentions")
    op.drop_index("saved_mentions_owner_category_created_idx", table_name="saved_mentions")
    op.drop_index("saved_mentions_owner_created_id_idx", table_name="saved_mentions")
    op.drop_table("saved_mentions")
    op.drop_index("provider_calls_job_created_idx", table_name="provider_calls")
    op.drop_table("provider_calls")
    op.drop_table("text_results")
    op.drop_index("artifacts_job_kind_created_idx", table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index("job_stage_runs_job_created_idx", table_name="job_stage_runs")
    op.drop_table("job_stage_runs")
    op.drop_index("jobs_owner_idempotency_uidx", table_name="jobs")
    op.drop_index("jobs_running_heartbeat_idx", table_name="jobs")
    op.drop_index("jobs_queued_claim_idx", table_name="jobs")
    op.drop_index("jobs_owner_created_id_idx", table_name="jobs")
    op.drop_table("jobs")
