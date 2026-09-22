"""drop legacy jobs, mentions, and job_events tables

Revision ID: 20260921_0017
Revises: 20260628_0016
Create Date: 2026-09-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260921_0017"
down_revision = "20260628_0016"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
API_OWNER_CHECK = "owner_id = current_setting('app.current_user_id', true)::uuid"


def upgrade() -> None:
    op.execute(
        """
        do $$
        begin
          if exists (
            select 1
            from pg_publication
            where pubname = 'supabase_realtime'
          ) and exists (
            select 1
            from pg_publication_tables
            where pubname = 'supabase_realtime'
              and schemaname = 'public'
              and tablename = 'job_events'
          ) then
            execute 'alter publication supabase_realtime drop table public.job_events';
          end if;
        end
        $$;
        """
    )
    op.execute("DROP POLICY IF EXISTS job_events_api_owner_delete ON public.job_events")
    op.execute("DROP POLICY IF EXISTS job_events_api_owner_select ON public.job_events")
    op.execute("DROP POLICY IF EXISTS job_events_worker_insert ON public.job_events")
    op.execute("DROP POLICY IF EXISTS job_events_owner_select ON public.job_events")
    op.execute(
        "REVOKE ALL ON TABLE public.job_events FROM authenticated, mentioned_api, mentioned_worker"
    )
    op.drop_index("job_events_owner_created_idx", table_name="job_events")
    op.drop_table("job_events")

    op.execute("DROP POLICY IF EXISTS mentions_api_owner_delete ON public.mentions")
    op.execute("DROP POLICY IF EXISTS mentions_worker_all ON public.mentions")
    op.execute("DROP POLICY IF EXISTS mentions_api_owner_update ON public.mentions")
    op.execute("DROP POLICY IF EXISTS mentions_api_owner_select ON public.mentions")
    op.execute("REVOKE ALL ON TABLE public.mentions FROM mentioned_api, mentioned_worker")
    op.drop_index("mentions_book_id_idx", table_name="mentions")
    op.drop_index("mentions_job_id_idx", table_name="mentions")
    op.drop_index("mentions_owner_created_idx", table_name="mentions")
    op.drop_table("mentions")

    op.execute("DROP POLICY IF EXISTS jobs_api_owner_delete ON public.jobs")
    op.execute("DROP POLICY IF EXISTS jobs_worker_all ON public.jobs")
    op.execute("DROP POLICY IF EXISTS jobs_api_owner_insert ON public.jobs")
    op.execute("DROP POLICY IF EXISTS jobs_api_owner_select ON public.jobs")
    op.execute("REVOKE ALL ON TABLE public.jobs FROM mentioned_api, mentioned_worker")
    op.drop_index("jobs_pending_claim_idx", table_name="jobs")
    op.drop_index("jobs_owner_created_idx", table_name="jobs")
    op.drop_table("jobs")

    # extract_jobs pgmq queue: drop only this queue's own tables/grants. The
    # pgmq schema USAGE, function EXECUTE grants, and "ALL SEQUENCES IN SCHEMA
    # pgmq" grants are shared with the still-live extract_sources and
    # push_notifications queues and must not be touched here.
    op.execute("REVOKE SELECT ON TABLE pgmq.a_extract_jobs FROM mentioned_worker")
    op.execute("REVOKE INSERT ON TABLE pgmq.a_extract_jobs FROM mentioned_worker")
    op.execute("REVOKE SELECT, UPDATE, DELETE ON TABLE pgmq.q_extract_jobs FROM mentioned_worker")
    op.execute("REVOKE SELECT, INSERT ON TABLE pgmq.q_extract_jobs FROM mentioned_api")
    op.execute(
        """
        do $$
        begin
          if exists (
            select 1
            from pgmq.list_queues()
            where queue_name = 'extract_jobs'
          ) then
            perform pgmq.drop_queue('extract_jobs');
          end if;
        end
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        do $$
        begin
          if not exists (
            select 1
            from pgmq.list_queues()
            where queue_name = 'extract_jobs'
          ) then
            perform pgmq.create('extract_jobs');
          end if;
        end
        $$;
        """
    )
    op.execute("GRANT SELECT, INSERT ON TABLE pgmq.q_extract_jobs TO mentioned_api")
    op.execute("GRANT SELECT, UPDATE, DELETE ON TABLE pgmq.q_extract_jobs TO mentioned_worker")
    op.execute("GRANT INSERT ON TABLE pgmq.a_extract_jobs TO mentioned_worker")
    op.execute("GRANT SELECT ON TABLE pgmq.a_extract_jobs TO mentioned_worker")

    op.create_table(
        "jobs",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("source_creator_handle", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
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

    op.create_table(
        "mentions",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("book_id", UUID, nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=False, server_default="book"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("google_books_url", sa.Text(), nullable=True),
        sa.Column("cover_image_url", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "category in ('book', 'product', 'place')", name="mentions_category_check"
        ),
        sa.CheckConstraint(
            "confidence is null or (confidence >= 0 and confidence <= 1)",
            name="mentions_confidence_check",
        ),
    )
    op.create_foreign_key(
        "mentions_book_id_fkey",
        "mentions",
        "books",
        ["book_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "mentions_owner_created_idx",
        "mentions",
        ["owner_id", sa.text("created_at DESC")],
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index("mentions_job_id_idx", "mentions", ["job_id"])
    op.create_index("mentions_book_id_idx", "mentions", ["book_id"])

    op.create_table(
        "job_events",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("job_id", UUID, nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name="job_events_job_id_fkey",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "event_type in ('job_done', 'job_failed')",
            name="job_events_event_type_check",
        ),
        sa.UniqueConstraint("job_id", name="job_events_job_id_key"),
    )
    op.create_index(
        "job_events_owner_created_idx",
        "job_events",
        ["owner_id", sa.text("created_at DESC")],
    )

    op.execute("ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.mentions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.job_events ENABLE ROW LEVEL SECURITY")

    op.execute("REVOKE ALL ON TABLE public.jobs, public.mentions FROM anon, authenticated")
    op.execute("REVOKE ALL ON TABLE public.job_events FROM anon, authenticated")

    op.execute("GRANT SELECT, INSERT, DELETE ON TABLE public.jobs TO mentioned_api")
    op.execute("GRANT SELECT, UPDATE ON TABLE public.jobs TO mentioned_worker")
    op.execute("GRANT SELECT, UPDATE, DELETE ON TABLE public.mentions TO mentioned_api")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE public.mentions TO mentioned_worker")
    op.execute("GRANT SELECT ON TABLE public.job_events TO authenticated")
    op.execute("GRANT INSERT ON TABLE public.job_events TO mentioned_worker")
    op.execute("GRANT SELECT, DELETE ON TABLE public.job_events TO mentioned_api")

    op.execute(
        f"""
        CREATE POLICY jobs_api_owner_select ON public.jobs
          FOR SELECT
          TO mentioned_api
          USING ({API_OWNER_CHECK})
        """
    )
    op.execute(
        f"""
        CREATE POLICY jobs_api_owner_insert ON public.jobs
          FOR INSERT
          TO mentioned_api
          WITH CHECK ({API_OWNER_CHECK})
        """
    )
    op.execute(
        f"""
        CREATE POLICY jobs_api_owner_delete ON public.jobs
          FOR DELETE
          TO mentioned_api
          USING ({API_OWNER_CHECK})
        """
    )
    op.execute(
        """
        CREATE POLICY jobs_worker_all ON public.jobs
          FOR ALL
          TO mentioned_worker
          USING (true)
          WITH CHECK (true)
        """
    )
    op.execute(
        f"""
        CREATE POLICY mentions_api_owner_select ON public.mentions
          FOR SELECT
          TO mentioned_api
          USING ({API_OWNER_CHECK})
        """
    )
    op.execute(
        f"""
        CREATE POLICY mentions_api_owner_update ON public.mentions
          FOR UPDATE
          TO mentioned_api
          USING ({API_OWNER_CHECK})
          WITH CHECK ({API_OWNER_CHECK})
        """
    )
    op.execute(
        f"""
        CREATE POLICY mentions_api_owner_delete ON public.mentions
          FOR DELETE
          TO mentioned_api
          USING ({API_OWNER_CHECK})
        """
    )
    op.execute(
        """
        CREATE POLICY mentions_worker_all ON public.mentions
          FOR ALL
          TO mentioned_worker
          USING (true)
          WITH CHECK (true)
        """
    )
    op.execute(
        """
        CREATE POLICY job_events_owner_select ON public.job_events
          FOR SELECT
          TO authenticated
          USING (owner_id = auth.uid())
        """
    )
    op.execute(
        """
        CREATE POLICY job_events_worker_insert ON public.job_events
          FOR INSERT
          TO mentioned_worker
          WITH CHECK (true)
        """
    )
    op.execute(
        f"""
        CREATE POLICY job_events_api_owner_select ON public.job_events
          FOR SELECT
          TO mentioned_api
          USING ({API_OWNER_CHECK})
        """
    )
    op.execute(
        f"""
        CREATE POLICY job_events_api_owner_delete ON public.job_events
          FOR DELETE
          TO mentioned_api
          USING ({API_OWNER_CHECK})
        """
    )

    op.execute(
        """
        do $$
        begin
          if exists (
            select 1
            from pg_publication
            where pubname = 'supabase_realtime'
          ) and not exists (
            select 1
            from pg_publication_tables
            where pubname = 'supabase_realtime'
              and schemaname = 'public'
              and tablename = 'job_events'
          ) then
            execute 'alter publication supabase_realtime add table public.job_events';
          end if;
        end
        $$;
        """
    )
