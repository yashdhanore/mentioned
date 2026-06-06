"""add job source creator handle

Revision ID: 20260606_0011
Revises: 20260523_0010
Create Date: 2026-06-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260606_0011"
down_revision = "20260523_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("source_creator_handle", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "source_creator_handle")
