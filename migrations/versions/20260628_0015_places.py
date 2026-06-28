"""add places table and source_items place columns

Revision ID: 20260628_0015
Revises: 781a3572bbaf
Create Date: 2026-06-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260628_0015"
down_revision = "781a3572bbaf"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
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
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "places_provider_place_unique_idx",
        "places",
        ["provider", "provider_place_id"],
        unique=True,
    )
    op.create_index("places_provider_idx", "places", ["provider"])
    op.create_index("places_provider_place_id_idx", "places", ["provider_place_id"])

    op.add_column("source_items", sa.Column("place_id", UUID, nullable=True))
    op.add_column("source_items", sa.Column("formatted_address", sa.Text(), nullable=True))
    op.add_column("source_items", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("source_items", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column("source_items", sa.Column("maps_url", sa.Text(), nullable=True))
    op.create_foreign_key(
        "source_items_place_id_fkey",
        "source_items",
        "places",
        ["place_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("source_items_place_id_idx", "source_items", ["place_id"])

    op.execute("REVOKE ALL ON TABLE public.places FROM anon, authenticated")
    op.execute("GRANT SELECT ON TABLE public.places TO mentioned_api")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE public.places TO mentioned_worker")


def downgrade() -> None:
    op.execute("REVOKE ALL ON TABLE public.places FROM mentioned_api, mentioned_worker")
    op.drop_index("source_items_place_id_idx", table_name="source_items")
    op.drop_constraint("source_items_place_id_fkey", "source_items", type_="foreignkey")
    op.drop_column("source_items", "maps_url")
    op.drop_column("source_items", "longitude")
    op.drop_column("source_items", "latitude")
    op.drop_column("source_items", "formatted_address")
    op.drop_column("source_items", "place_id")
    op.drop_index("places_provider_place_id_idx", table_name="places")
    op.drop_index("places_provider_idx", table_name="places")
    op.drop_index("places_provider_place_unique_idx", table_name="places")
    op.drop_table("places")
