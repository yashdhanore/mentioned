"""initial schema

Revision ID: 20260922_0018
Revises:
Create Date: 2026-09-22

Squash of the 16 revisions from 20260504_0003 through 20260922_0018 (including the
hash-named 781a3572bbaf), collapsed to the net live schema: books, places, sources,
source_items, saved_sources, push_tokens, waitlist_signups, and the extract_sources/
push_notifications pgmq queues. The legacy jobs/mentions/job_events tables and the
extract_jobs queue were created and later dropped within that chain, so they are not
recreated here. The revision id is kept as 20260922_0018 (the old chain's head) so
production's alembic_version needs no stamp; the next real revision continues as
20260923_0019.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260922_0018"
down_revision = None
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
JSONB = postgresql.JSONB(astext_type=sa.Text())
API_OWNER_CHECK = "owner_id = current_setting('app.current_user_id', true)::uuid"


def upgrade() -> None:
    op.execute("GRANT USAGE ON SCHEMA public TO mentioned_api, mentioned_worker")

    # books
    op.create_table(
        "books",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("provider", sa.Text(), nullable=False, server_default="google_books"),
        sa.Column("provider_volume_id", sa.Text(), nullable=False),
        sa.Column("provider_etag", sa.Text(), nullable=True),
        sa.Column("provider_self_link", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("subtitle", sa.Text(), nullable=True),
        sa.Column("authors", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("publisher", sa.Text(), nullable=True),
        sa.Column("published_date", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "industry_identifiers",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("isbn_10", sa.Text(), nullable=True),
        sa.Column("isbn_13", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("print_type", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("main_category", sa.Text(), nullable=True),
        sa.Column("categories", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("image_links", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("cover_image_url", sa.Text(), nullable=True),
        sa.Column("preview_link", sa.Text(), nullable=True),
        sa.Column("info_link", sa.Text(), nullable=True),
        sa.Column("canonical_volume_link", sa.Text(), nullable=True),
        sa.Column("sale_info", JSONB, nullable=True),
        sa.Column("access_info", JSONB, nullable=True),
        sa.Column("raw_provider_payload", JSONB, nullable=True),
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
    )
    op.create_index(
        "books_provider_volume_unique_idx", "books", ["provider", "provider_volume_id"], unique=True
    )
    op.create_index("books_provider_idx", "books", ["provider"])
    op.create_index("books_provider_volume_id_idx", "books", ["provider_volume_id"])
    op.create_index("books_isbn_10_idx", "books", ["isbn_10"])
    op.create_index("books_isbn_13_idx", "books", ["isbn_13"])
    op.execute("REVOKE ALL ON TABLE public.books FROM anon, authenticated")
    op.execute("GRANT SELECT ON TABLE public.books TO mentioned_api")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE public.books TO mentioned_worker")

    # places
    op.create_table(
        "places",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("provider", sa.Text(), nullable=False, server_default="google_places"),
        sa.Column("provider_place_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("formatted_address", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("maps_url", sa.Text(), nullable=True),
        sa.Column("raw_provider_payload", JSONB, nullable=True),
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
    )
    op.create_index(
        "places_provider_place_unique_idx",
        "places",
        ["provider", "provider_place_id"],
        unique=True,
    )
    op.create_index("places_provider_idx", "places", ["provider"])
    op.create_index("places_provider_place_id_idx", "places", ["provider_place_id"])
    op.execute("REVOKE ALL ON TABLE public.places FROM anon, authenticated")
    op.execute("GRANT SELECT ON TABLE public.places TO mentioned_api")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE public.places TO mentioned_worker")

    # sources
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
        sa.Column("skip_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status in ('pending', 'processing', 'done', 'failed')", name="sources_status_check"
        ),
        sa.UniqueConstraint("source_key", name="sources_source_key_key"),
    )
    op.create_index("sources_platform_idx", "sources", ["platform"])
    op.create_index("sources_status_idx", "sources", ["status"])

    # source_items
    op.create_table(
        "source_items",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "source_id", UUID, sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("book_id", UUID, sa.ForeignKey("books.id", ondelete="SET NULL"), nullable=True),
        sa.Column("category", sa.Text(), nullable=False, server_default="book"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("google_books_url", sa.Text(), nullable=True),
        sa.Column("cover_image_url", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
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
        sa.Column("place_id", UUID, sa.ForeignKey("places.id", ondelete="SET NULL"), nullable=True),
        sa.Column("formatted_address", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("maps_url", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "category in ('book', 'product', 'place')", name="source_items_category_check"
        ),
        sa.CheckConstraint(
            "confidence is null or (confidence >= 0 and confidence <= 1)",
            name="source_items_confidence_check",
        ),
    )
    op.create_index("source_items_source_position_idx", "source_items", ["source_id", "position"])
    op.create_index("source_items_book_id_idx", "source_items", ["book_id"])
    op.create_index("source_items_category_idx", "source_items", ["category"])
    op.create_index("source_items_place_id_idx", "source_items", ["place_id"])

    # saved_sources
    op.create_table(
        "saved_sources",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column(
            "source_id", UUID, sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_burst_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_burst_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_daily_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_daily_count", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("owner_id", "source_id", name="saved_sources_owner_source_key"),
    )
    op.create_index(
        "saved_sources_owner_created_idx", "saved_sources", ["owner_id", sa.text("created_at DESC")]
    )
    op.create_index("saved_sources_source_id_idx", "saved_sources", ["source_id"])

    op.execute("ALTER TABLE public.sources ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.source_items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.saved_sources ENABLE ROW LEVEL SECURITY")
    op.execute(
        "REVOKE ALL ON TABLE public.sources, public.source_items, public.saved_sources "
        "FROM anon, authenticated"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE public.sources TO mentioned_api")
    op.execute("GRANT SELECT ON TABLE public.source_items TO mentioned_api")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.sources, public.source_items TO mentioned_worker"
    )
    op.execute("GRANT DELETE ON TABLE public.source_items TO mentioned_worker")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.saved_sources TO mentioned_api"
    )
    op.execute("GRANT SELECT, INSERT, DELETE ON TABLE public.saved_sources TO mentioned_worker")

    op.execute(
        "CREATE POLICY sources_api_select ON public.sources FOR SELECT TO mentioned_api USING (true)"
    )
    op.execute(
        "CREATE POLICY sources_api_insert ON public.sources FOR INSERT TO mentioned_api "
        "WITH CHECK (true)"
    )
    op.execute(
        "CREATE POLICY sources_api_retry_update ON public.sources FOR UPDATE TO mentioned_api "
        "USING (true) WITH CHECK (true)"
    )
    op.execute(
        "CREATE POLICY source_items_api_select ON public.source_items FOR SELECT TO mentioned_api "
        "USING (true)"
    )
    op.execute(
        f"""
        CREATE POLICY saved_sources_api_owner_all ON public.saved_sources
          FOR ALL
          TO mentioned_api
          USING ({API_OWNER_CHECK})
          WITH CHECK ({API_OWNER_CHECK})
        """
    )
    op.execute(
        "CREATE POLICY sources_worker_all ON public.sources FOR ALL TO mentioned_worker "
        "USING (true) WITH CHECK (true)"
    )
    op.execute(
        "CREATE POLICY source_items_worker_all ON public.source_items FOR ALL TO mentioned_worker "
        "USING (true) WITH CHECK (true)"
    )
    op.execute(
        "CREATE POLICY saved_sources_worker_all ON public.saved_sources FOR ALL TO mentioned_worker "
        "USING (true) WITH CHECK (true)"
    )

    # push_tokens
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
        sa.CheckConstraint("platform in ('ios', 'android')", name="push_tokens_platform_check"),
        sa.UniqueConstraint(
            "owner_id", "expo_push_token", name="push_tokens_owner_expo_push_token_key"
        ),
    )
    op.create_index(
        "push_tokens_owner_active_idx",
        "push_tokens",
        ["owner_id"],
        postgresql_where=sa.text("disabled_at IS NULL"),
    )
    op.create_index("push_tokens_expo_push_token_idx", "push_tokens", ["expo_push_token"])

    op.execute("ALTER TABLE public.push_tokens ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON TABLE public.push_tokens FROM anon, authenticated")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.push_tokens TO mentioned_api")
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
        f"""
        CREATE POLICY push_tokens_api_owner_delete ON public.push_tokens
          FOR DELETE
          TO mentioned_api
          USING ({API_OWNER_CHECK})
        """
    )
    op.execute(
        "CREATE POLICY push_tokens_worker_select ON public.push_tokens FOR SELECT "
        "TO mentioned_worker USING (true)"
    )
    op.execute(
        "CREATE POLICY push_tokens_worker_update ON public.push_tokens FOR UPDATE "
        "TO mentioned_worker USING (true) WITH CHECK (true)"
    )

    # waitlist_signups
    op.execute(
        """
        CREATE TABLE public.waitlist_signups (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            email text NOT NULL,
            source text,
            user_agent text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT waitlist_signups_email_normalized CHECK (email = lower(trim(email))),
            CONSTRAINT waitlist_signups_email_not_blank CHECK (length(email) > 3),
            CONSTRAINT waitlist_signups_source_length
                CHECK (source IS NULL OR length(source) <= 120)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX waitlist_signups_email_lower_idx "
        "ON public.waitlist_signups (lower(email))"
    )
    op.execute("ALTER TABLE public.waitlist_signups ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON TABLE public.waitlist_signups FROM anon, authenticated")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE public.waitlist_signups TO mentioned_api")
    op.execute(
        """
        CREATE POLICY waitlist_signups_api_manage ON public.waitlist_signups
          FOR ALL
          TO mentioned_api
          USING (true)
          WITH CHECK (true)
        """
    )

    # pgmq: extension, shared schema-level grants, and the two live queues
    op.execute("create extension if not exists pgmq")
    op.execute("GRANT USAGE ON SCHEMA pgmq TO mentioned_api, mentioned_worker")
    op.execute(
        "GRANT EXECUTE ON FUNCTION pgmq.send(text, jsonb, integer) TO mentioned_api, mentioned_worker"
    )
    op.execute(
        """
        GRANT EXECUTE ON FUNCTION pgmq.read_with_poll(text, integer, integer, integer, integer, jsonb)
        TO mentioned_worker
        """
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION pgmq.read(text, integer, integer, jsonb) TO mentioned_worker"
    )
    op.execute("GRANT EXECUTE ON FUNCTION pgmq.archive(text, bigint) TO mentioned_worker")
    op.execute("GRANT USAGE ON TYPE pgmq.message_record TO mentioned_worker")
    op.execute(
        "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA pgmq TO mentioned_api, mentioned_worker"
    )

    op.execute("select pgmq.create('extract_sources')")
    op.execute("GRANT SELECT, INSERT ON TABLE pgmq.q_extract_sources TO mentioned_api")
    op.execute("GRANT SELECT, UPDATE, DELETE ON TABLE pgmq.q_extract_sources TO mentioned_worker")
    op.execute("GRANT SELECT, INSERT ON TABLE pgmq.a_extract_sources TO mentioned_worker")

    op.execute("select pgmq.create('push_notifications')")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE pgmq.q_push_notifications TO mentioned_worker"
    )
    op.execute("GRANT SELECT, INSERT ON TABLE pgmq.a_push_notifications TO mentioned_worker")


def downgrade() -> None:
    op.execute("select pgmq.drop_queue('push_notifications')")
    op.execute("select pgmq.drop_queue('extract_sources')")
    op.execute(
        "REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA pgmq FROM mentioned_api, mentioned_worker"
    )
    op.execute("REVOKE USAGE ON TYPE pgmq.message_record FROM mentioned_worker")
    op.execute("REVOKE EXECUTE ON FUNCTION pgmq.archive(text, bigint) FROM mentioned_worker")
    op.execute(
        "REVOKE EXECUTE ON FUNCTION pgmq.read(text, integer, integer, jsonb) FROM mentioned_worker"
    )
    op.execute(
        """
        REVOKE EXECUTE ON FUNCTION pgmq.read_with_poll(text, integer, integer, integer, integer, jsonb)
        FROM mentioned_worker
        """
    )
    op.execute(
        "REVOKE EXECUTE ON FUNCTION pgmq.send(text, jsonb, integer) FROM mentioned_api, mentioned_worker"
    )
    op.execute("REVOKE USAGE ON SCHEMA pgmq FROM mentioned_api, mentioned_worker")

    op.execute("DROP POLICY IF EXISTS waitlist_signups_api_manage ON public.waitlist_signups")
    op.execute("REVOKE ALL ON TABLE public.waitlist_signups FROM mentioned_api")
    op.execute("DROP TABLE public.waitlist_signups")

    op.execute("DROP POLICY IF EXISTS push_tokens_worker_update ON public.push_tokens")
    op.execute("DROP POLICY IF EXISTS push_tokens_worker_select ON public.push_tokens")
    op.execute("DROP POLICY IF EXISTS push_tokens_api_owner_delete ON public.push_tokens")
    op.execute("DROP POLICY IF EXISTS push_tokens_api_owner_update ON public.push_tokens")
    op.execute("DROP POLICY IF EXISTS push_tokens_api_owner_insert ON public.push_tokens")
    op.execute("DROP POLICY IF EXISTS push_tokens_api_owner_select ON public.push_tokens")
    op.execute("REVOKE ALL ON TABLE public.push_tokens FROM mentioned_api, mentioned_worker")
    op.drop_index("push_tokens_expo_push_token_idx", table_name="push_tokens")
    op.drop_index("push_tokens_owner_active_idx", table_name="push_tokens")
    op.drop_table("push_tokens")

    op.execute("DROP POLICY IF EXISTS saved_sources_worker_all ON public.saved_sources")
    op.execute("DROP POLICY IF EXISTS source_items_worker_all ON public.source_items")
    op.execute("DROP POLICY IF EXISTS sources_worker_all ON public.sources")
    op.execute("DROP POLICY IF EXISTS saved_sources_api_owner_all ON public.saved_sources")
    op.execute("DROP POLICY IF EXISTS source_items_api_select ON public.source_items")
    op.execute("DROP POLICY IF EXISTS sources_api_retry_update ON public.sources")
    op.execute("DROP POLICY IF EXISTS sources_api_insert ON public.sources")
    op.execute("DROP POLICY IF EXISTS sources_api_select ON public.sources")
    op.execute(
        "REVOKE ALL ON TABLE public.sources, public.source_items, public.saved_sources "
        "FROM mentioned_api, mentioned_worker"
    )
    op.drop_index("saved_sources_source_id_idx", table_name="saved_sources")
    op.drop_index("saved_sources_owner_created_idx", table_name="saved_sources")
    op.drop_table("saved_sources")
    op.drop_index("source_items_place_id_idx", table_name="source_items")
    op.drop_index("source_items_category_idx", table_name="source_items")
    op.drop_index("source_items_book_id_idx", table_name="source_items")
    op.drop_index("source_items_source_position_idx", table_name="source_items")
    op.drop_table("source_items")
    op.drop_index("sources_status_idx", table_name="sources")
    op.drop_index("sources_platform_idx", table_name="sources")
    op.drop_table("sources")

    op.execute("REVOKE ALL ON TABLE public.places FROM mentioned_api, mentioned_worker")
    op.drop_index("places_provider_place_id_idx", table_name="places")
    op.drop_index("places_provider_idx", table_name="places")
    op.drop_index("places_provider_place_unique_idx", table_name="places")
    op.drop_table("places")

    op.execute("REVOKE ALL ON TABLE public.books FROM mentioned_api, mentioned_worker")
    op.drop_index("books_isbn_13_idx", table_name="books")
    op.drop_index("books_isbn_10_idx", table_name="books")
    op.drop_index("books_provider_volume_id_idx", table_name="books")
    op.drop_index("books_provider_idx", table_name="books")
    op.drop_index("books_provider_volume_unique_idx", table_name="books")
    op.drop_table("books")

    op.execute("REVOKE USAGE ON SCHEMA public FROM mentioned_api, mentioned_worker")
