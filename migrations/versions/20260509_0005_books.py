"""add normalized books and mention links

Revision ID: 20260509_0005
Revises: 20260505_0004
Create Date: 2026-05-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260509_0005"
down_revision = "20260505_0004"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
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
        "books_provider_volume_unique_idx",
        "books",
        ["provider", "provider_volume_id"],
        unique=True,
    )
    op.create_index("books_provider_idx", "books", ["provider"])
    op.create_index("books_provider_volume_id_idx", "books", ["provider_volume_id"])
    op.create_index("books_isbn_10_idx", "books", ["isbn_10"])
    op.create_index("books_isbn_13_idx", "books", ["isbn_13"])

    op.add_column("mentions", sa.Column("book_id", UUID, nullable=True))
    op.create_foreign_key(
        "mentions_book_id_fkey",
        "mentions",
        "books",
        ["book_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("mentions_book_id_idx", "mentions", ["book_id"])

    op.execute("REVOKE ALL ON TABLE public.books FROM anon, authenticated")
    op.execute("GRANT SELECT ON TABLE public.books TO mentioned_api")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE public.books TO mentioned_worker")


def downgrade() -> None:
    op.execute("REVOKE ALL ON TABLE public.books FROM mentioned_api, mentioned_worker")
    op.drop_index("mentions_book_id_idx", table_name="mentions")
    op.drop_constraint("mentions_book_id_fkey", "mentions", type_="foreignkey")
    op.drop_column("mentions", "book_id")
    op.drop_index("books_isbn_13_idx", table_name="books")
    op.drop_index("books_isbn_10_idx", table_name="books")
    op.drop_index("books_provider_volume_id_idx", table_name="books")
    op.drop_index("books_provider_idx", table_name="books")
    op.drop_index("books_provider_volume_unique_idx", table_name="books")
    op.drop_table("books")
