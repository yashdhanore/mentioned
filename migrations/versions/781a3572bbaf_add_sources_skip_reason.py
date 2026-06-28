"""add sources skip_reason

Revision ID: 781a3572bbaf
Revises: 20260622_0014
Create Date: 2026-06-24 23:29:36.876557
"""

from alembic import op
import sqlalchemy as sa



revision = '781a3572bbaf'
down_revision = '20260622_0014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("skip_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "skip_reason")
