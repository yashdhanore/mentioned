"""allow worker to archive queue messages with returning

Revision ID: 20260513_0007
Revises: 20260512_0006
Create Date: 2026-05-13
"""

from __future__ import annotations

from alembic import op


revision = "20260513_0007"
down_revision = "20260512_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT SELECT ON TABLE pgmq.a_extract_jobs TO mentioned_worker")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON TABLE pgmq.a_extract_jobs FROM mentioned_worker")
