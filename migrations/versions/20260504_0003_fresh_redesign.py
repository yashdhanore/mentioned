"""fresh redesign: 2 tables, 3 states

Revision ID: 20260504_0003
Revises:
Create Date: 2026-05-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260504_0003"
down_revision = None
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)


def upgrade() -> None:
    # Create new jobs table
    op.create_table(
        "jobs",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.Text(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('pending', 'done', 'failed')", name="jobs_status_check"),
    )
    op.create_index(
        "jobs_owner_created_idx",
        "jobs",
        ["owner_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "jobs_pending_claim_idx",
        "jobs",
        ["created_at"],
        postgresql_where=sa.text("status = 'pending' AND locked_by IS NULL"),
    )

    # Create new mentions table
    op.create_table(
        "mentions",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=False, server_default="book"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("google_books_url", sa.Text(), nullable=True),
        sa.Column("cover_image_url", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("category in ('book', 'product', 'place')", name="mentions_category_check"),
        sa.CheckConstraint(
            "confidence is null or (confidence >= 0 and confidence <= 1)",
            name="mentions_confidence_check",
        ),
    )
    op.create_index(
        "mentions_owner_created_idx",
        "mentions",
        ["owner_id", sa.text("created_at DESC")],
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index("mentions_job_id_idx", "mentions", ["job_id"])

    # RLS policies
    for table_name in ("jobs", "mentions"):
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY jobs_owner_policy ON jobs
          FOR ALL
          USING (owner_id = current_setting('app.current_user_id')::uuid)
          WITH CHECK (owner_id = current_setting('app.current_user_id')::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY mentions_owner_policy ON mentions
          FOR ALL
          USING (owner_id = current_setting('app.current_user_id')::uuid)
          WITH CHECK (owner_id = current_setting('app.current_user_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS mentions_owner_policy ON mentions")
    op.execute("DROP POLICY IF EXISTS jobs_owner_policy ON jobs")
    op.drop_index("mentions_job_id_idx", table_name="mentions")
    op.drop_index("mentions_owner_created_idx", table_name="mentions")
    op.drop_table("mentions")
    op.drop_index("jobs_pending_claim_idx", table_name="jobs")
    op.drop_index("jobs_owner_created_idx", table_name="jobs")
    op.drop_table("jobs")
