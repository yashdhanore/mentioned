"""add push notification tokens and queue

Revision ID: 20260514_0009
Revises: 20260513_0008
Create Date: 2026-05-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260514_0009"
down_revision = "20260513_0008"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
API_OWNER_CHECK = "owner_id = current_setting('app.current_user_id', true)::uuid"


def upgrade() -> None:
    op.create_table(
        "push_tokens",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("expo_push_token", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "platform in ('ios', 'android')",
            name="push_tokens_platform_check",
        ),
        sa.UniqueConstraint(
            "owner_id",
            "expo_push_token",
            name="push_tokens_owner_expo_push_token_key",
        ),
    )
    op.create_index(
        "push_tokens_owner_active_idx",
        "push_tokens",
        ["owner_id"],
        postgresql_where=sa.text("disabled_at IS NULL"),
    )
    op.create_index(
        "push_tokens_expo_push_token_idx",
        "push_tokens",
        ["expo_push_token"],
    )

    op.execute("ALTER TABLE public.push_tokens ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON TABLE public.push_tokens FROM anon, authenticated")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE public.push_tokens TO mentioned_api")
    op.execute("GRANT SELECT, UPDATE ON TABLE public.push_tokens TO mentioned_worker")

    op.execute(
        f"""
        CREATE POLICY push_tokens_api_owner_select ON public.push_tokens
          FOR SELECT
          TO mentioned_api
          USING ({API_OWNER_CHECK})
        """
    )
    op.execute(
        f"""
        CREATE POLICY push_tokens_api_owner_insert ON public.push_tokens
          FOR INSERT
          TO mentioned_api
          WITH CHECK ({API_OWNER_CHECK})
        """
    )
    op.execute(
        f"""
        CREATE POLICY push_tokens_api_owner_update ON public.push_tokens
          FOR UPDATE
          TO mentioned_api
          USING ({API_OWNER_CHECK})
          WITH CHECK ({API_OWNER_CHECK})
        """
    )
    op.execute(
        """
        CREATE POLICY push_tokens_worker_select ON public.push_tokens
          FOR SELECT
          TO mentioned_worker
          USING (true)
        """
    )
    op.execute(
        """
        CREATE POLICY push_tokens_worker_update ON public.push_tokens
          FOR UPDATE
          TO mentioned_worker
          USING (true)
          WITH CHECK (true)
        """
    )

    op.execute("create extension if not exists pgmq")
    op.execute(
        """
        do $$
        begin
          if not exists (
            select 1
            from pgmq.list_queues()
            where queue_name = 'push_notifications'
          ) then
            perform pgmq.create('push_notifications');
          end if;
        end
        $$;
        """
    )

    op.execute("GRANT USAGE ON SCHEMA pgmq TO mentioned_worker")
    op.execute("GRANT EXECUTE ON FUNCTION pgmq.send(text, jsonb, integer) TO mentioned_worker")
    op.execute(
        "GRANT EXECUTE ON FUNCTION pgmq.read(text, integer, integer, jsonb) TO mentioned_worker"
    )
    op.execute("GRANT EXECUTE ON FUNCTION pgmq.archive(text, bigint) TO mentioned_worker")
    op.execute("GRANT USAGE ON TYPE pgmq.message_record TO mentioned_worker")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE pgmq.q_push_notifications TO mentioned_worker"
    )
    op.execute("GRANT SELECT, INSERT ON TABLE pgmq.a_push_notifications TO mentioned_worker")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA pgmq TO mentioned_worker")


def downgrade() -> None:
    op.execute("REVOKE SELECT, INSERT ON TABLE pgmq.a_push_notifications FROM mentioned_worker")
    op.execute(
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLE pgmq.q_push_notifications FROM mentioned_worker"
    )
    op.execute(
        "REVOKE EXECUTE ON FUNCTION pgmq.read(text, integer, integer, jsonb) FROM mentioned_worker"
    )
    op.execute("REVOKE EXECUTE ON FUNCTION pgmq.send(text, jsonb, integer) FROM mentioned_worker")
    op.execute("select pgmq.drop_queue('push_notifications')")

    op.execute("DROP POLICY IF EXISTS push_tokens_worker_update ON public.push_tokens")
    op.execute("DROP POLICY IF EXISTS push_tokens_worker_select ON public.push_tokens")
    op.execute("DROP POLICY IF EXISTS push_tokens_api_owner_update ON public.push_tokens")
    op.execute("DROP POLICY IF EXISTS push_tokens_api_owner_insert ON public.push_tokens")
    op.execute("DROP POLICY IF EXISTS push_tokens_api_owner_select ON public.push_tokens")
    op.execute("REVOKE ALL ON TABLE public.push_tokens FROM mentioned_api, mentioned_worker")
    op.drop_index("push_tokens_expo_push_token_idx", table_name="push_tokens")
    op.drop_index("push_tokens_owner_active_idx", table_name="push_tokens")
    op.drop_table("push_tokens")
