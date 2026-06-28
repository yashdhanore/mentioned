"""grant worker delete on source_items

Revision ID: 20260628_0016
Revises: 20260628_0015
Create Date: 2026-06-28
"""

from __future__ import annotations

from alembic import op


revision = "20260628_0016"
down_revision = "20260628_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # complete_source_processing replaces a source's items by deleting the
    # existing rows before re-inserting. The worker's grant on source_items was
    # SELECT, INSERT, UPDATE only; the source_items_worker_all RLS policy
    # already covers DELETE, but the table-level grant did not.
    op.execute("GRANT DELETE ON TABLE public.source_items TO mentioned_worker")


def downgrade() -> None:
    op.execute("REVOKE DELETE ON TABLE public.source_items FROM mentioned_worker")
