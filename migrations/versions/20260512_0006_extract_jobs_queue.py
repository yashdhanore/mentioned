"""add extract jobs queue

Revision ID: 20260512_0006
Revises: 20260509_0005
Create Date: 2026-05-12
"""

from __future__ import annotations

from alembic import op


revision = "20260512_0006"
down_revision = "20260509_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("create extension if not exists pgmq")
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

    op.execute("GRANT USAGE ON SCHEMA pgmq TO mentioned_api, mentioned_worker")
    op.execute("GRANT EXECUTE ON FUNCTION pgmq.send(text, jsonb, integer) TO mentioned_api")
    op.execute(
        """
        GRANT EXECUTE ON FUNCTION pgmq.read_with_poll(text, integer, integer, integer, integer, jsonb)
        TO mentioned_worker
        """
    )
    op.execute("GRANT EXECUTE ON FUNCTION pgmq.archive(text, bigint) TO mentioned_worker")
    op.execute("GRANT USAGE ON TYPE pgmq.message_record TO mentioned_worker")

    op.execute("GRANT SELECT, INSERT ON TABLE pgmq.q_extract_jobs TO mentioned_api")
    op.execute("GRANT SELECT, UPDATE, DELETE ON TABLE pgmq.q_extract_jobs TO mentioned_worker")
    op.execute("GRANT INSERT ON TABLE pgmq.a_extract_jobs TO mentioned_worker")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA pgmq TO mentioned_api, mentioned_worker")


def downgrade() -> None:
    op.execute("REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA pgmq FROM mentioned_api, mentioned_worker")
    op.execute("REVOKE INSERT ON TABLE pgmq.a_extract_jobs FROM mentioned_worker")
    op.execute("REVOKE SELECT, UPDATE, DELETE ON TABLE pgmq.q_extract_jobs FROM mentioned_worker")
    op.execute("REVOKE SELECT, INSERT ON TABLE pgmq.q_extract_jobs FROM mentioned_api")
    op.execute("REVOKE USAGE ON TYPE pgmq.message_record FROM mentioned_worker")
    op.execute("REVOKE EXECUTE ON FUNCTION pgmq.archive(text, bigint) FROM mentioned_worker")
    op.execute(
        """
        REVOKE EXECUTE ON FUNCTION pgmq.read_with_poll(text, integer, integer, integer, integer, jsonb)
        FROM mentioned_worker
        """
    )
    op.execute("REVOKE EXECUTE ON FUNCTION pgmq.send(text, jsonb, integer) FROM mentioned_api")
    op.execute("REVOKE USAGE ON SCHEMA pgmq FROM mentioned_api, mentioned_worker")
    op.execute("select pgmq.drop_queue('extract_jobs')")
