"""add canonical sources and saved sources

Revision ID: 20260622_0014
Revises: 20260613_0013
Create Date: 2026-06-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260622_0014"
down_revision = "20260613_0013"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_key", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("creator_handle", sa.Text(), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status in ('pending', 'processing', 'done', 'failed')", name="sources_status_check"),
        sa.UniqueConstraint("source_key", name="sources_source_key_key"),
    )
    op.create_index("sources_platform_idx", "sources", ["platform"])
    op.create_index("sources_status_idx", "sources", ["status"])

    op.create_table(
        "source_items",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", UUID, sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("book_id", UUID, sa.ForeignKey("books.id", ondelete="SET NULL"), nullable=True),
        sa.Column("category", sa.Text(), nullable=False, server_default="book"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("google_books_url", sa.Text(), nullable=True),
        sa.Column("cover_image_url", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("category in ('book', 'product', 'place')", name="source_items_category_check"),
        sa.CheckConstraint(
            "confidence is null or (confidence >= 0 and confidence <= 1)",
            name="source_items_confidence_check",
        ),
    )
    op.create_index("source_items_source_position_idx", "source_items", ["source_id", "position"])
    op.create_index("source_items_book_id_idx", "source_items", ["book_id"])
    op.create_index("source_items_category_idx", "source_items", ["category"])

    op.create_table(
        "saved_sources",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("source_id", UUID, sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_burst_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_burst_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_daily_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_daily_count", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("owner_id", "source_id", name="saved_sources_owner_source_key"),
    )
    op.create_index("saved_sources_owner_created_idx", "saved_sources", ["owner_id", sa.text("created_at DESC")])
    op.create_index("saved_sources_source_id_idx", "saved_sources", ["source_id"])

    op.execute("ALTER TABLE public.sources ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.source_items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.saved_sources ENABLE ROW LEVEL SECURITY")

    op.execute("REVOKE ALL ON TABLE public.sources, public.source_items, public.saved_sources FROM anon, authenticated")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE public.sources TO mentioned_api")
    op.execute("GRANT SELECT ON TABLE public.source_items TO mentioned_api")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE public.sources, public.source_items TO mentioned_worker")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.saved_sources TO mentioned_api")
    op.execute("GRANT SELECT, INSERT, DELETE ON TABLE public.saved_sources TO mentioned_worker")

    op.execute("CREATE POLICY sources_api_select ON public.sources FOR SELECT TO mentioned_api USING (true)")
    op.execute("CREATE POLICY sources_api_insert ON public.sources FOR INSERT TO mentioned_api WITH CHECK (true)")
    op.execute("CREATE POLICY sources_api_retry_update ON public.sources FOR UPDATE TO mentioned_api USING (true) WITH CHECK (true)")
    op.execute("CREATE POLICY source_items_api_select ON public.source_items FOR SELECT TO mentioned_api USING (true)")
    op.execute(
        """
        CREATE POLICY saved_sources_api_owner_all ON public.saved_sources
          FOR ALL
          TO mentioned_api
          USING (owner_id = current_setting('app.current_user_id', true)::uuid)
          WITH CHECK (owner_id = current_setting('app.current_user_id', true)::uuid)
        """
    )
    op.execute("CREATE POLICY sources_worker_all ON public.sources FOR ALL TO mentioned_worker USING (true) WITH CHECK (true)")
    op.execute("CREATE POLICY source_items_worker_all ON public.source_items FOR ALL TO mentioned_worker USING (true) WITH CHECK (true)")
    op.execute("CREATE POLICY saved_sources_worker_all ON public.saved_sources FOR ALL TO mentioned_worker USING (true) WITH CHECK (true)")

    op.execute("create extension if not exists pgmq")
    op.execute(
        """
        do $$
        begin
          if not exists (
            select 1
            from pgmq.list_queues()
            where queue_name = 'extract_sources'
          ) then
            perform pgmq.create('extract_sources');
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

    op.execute("GRANT SELECT, INSERT ON TABLE pgmq.q_extract_sources TO mentioned_api")
    op.execute("GRANT SELECT, UPDATE, DELETE ON TABLE pgmq.q_extract_sources TO mentioned_worker")
    op.execute("GRANT SELECT, INSERT ON TABLE pgmq.a_extract_sources TO mentioned_worker")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA pgmq TO mentioned_api, mentioned_worker")


def downgrade() -> None:
    op.execute("REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA pgmq FROM mentioned_api, mentioned_worker")
    op.execute("REVOKE SELECT, INSERT ON TABLE pgmq.a_extract_sources FROM mentioned_worker")
    op.execute("REVOKE SELECT, UPDATE, DELETE ON TABLE pgmq.q_extract_sources FROM mentioned_worker")
    op.execute("REVOKE SELECT, INSERT ON TABLE pgmq.q_extract_sources FROM mentioned_api")
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
    op.execute("select pgmq.drop_queue('extract_sources')")

    op.execute("DROP POLICY IF EXISTS saved_sources_worker_all ON public.saved_sources")
    op.execute("DROP POLICY IF EXISTS source_items_worker_all ON public.source_items")
    op.execute("DROP POLICY IF EXISTS sources_worker_all ON public.sources")
    op.execute("DROP POLICY IF EXISTS saved_sources_api_owner_all ON public.saved_sources")
    op.execute("DROP POLICY IF EXISTS source_items_api_select ON public.source_items")
    op.execute("DROP POLICY IF EXISTS sources_api_retry_update ON public.sources")
    op.execute("DROP POLICY IF EXISTS sources_api_insert ON public.sources")
    op.execute("DROP POLICY IF EXISTS sources_api_select ON public.sources")
    op.execute("REVOKE ALL ON TABLE public.sources, public.source_items, public.saved_sources FROM mentioned_api, mentioned_worker")
    op.drop_index("saved_sources_source_id_idx", table_name="saved_sources")
    op.drop_index("saved_sources_owner_created_idx", table_name="saved_sources")
    op.drop_table("saved_sources")
    op.drop_index("source_items_category_idx", table_name="source_items")
    op.drop_index("source_items_book_id_idx", table_name="source_items")
    op.drop_index("source_items_source_position_idx", table_name="source_items")
    op.drop_table("source_items")
    op.drop_index("sources_status_idx", table_name="sources")
    op.drop_index("sources_platform_idx", table_name="sources")
    op.drop_table("sources")
