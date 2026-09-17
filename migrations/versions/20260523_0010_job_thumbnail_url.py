"""add job thumbnail url

Revision ID: 20260523_0010
Revises: 20260514_0009
Create Date: 2026-05-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260523_0010"
down_revision = "20260514_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("thumbnail_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "thumbnail_url")
