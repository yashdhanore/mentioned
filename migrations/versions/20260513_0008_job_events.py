"""add realtime job events

Revision ID: 20260513_0008
Revises: 20260513_0007
Create Date: 2026-05-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260513_0008"
down_revision = "20260513_0007"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)


def upgrade() -> None:
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

    op.execute("ALTER TABLE public.job_events ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON TABLE public.job_events FROM anon, authenticated")
    op.execute("GRANT SELECT ON TABLE public.job_events TO authenticated")
    op.execute("GRANT INSERT ON TABLE public.job_events TO mentioned_worker")

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


def downgrade() -> None:
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
    op.execute("DROP POLICY IF EXISTS job_events_worker_insert ON public.job_events")
    op.execute("DROP POLICY IF EXISTS job_events_owner_select ON public.job_events")
    op.execute("REVOKE ALL ON TABLE public.job_events FROM authenticated, mentioned_worker")
    op.drop_index("job_events_owner_created_idx", table_name="job_events")
    op.drop_table("job_events")
