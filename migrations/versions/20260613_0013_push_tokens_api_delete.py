"""allow api hard delete of push tokens on account deletion

Revision ID: 20260613_0013
Revises: 20260606_0012
Create Date: 2026-06-13
"""

from __future__ import annotations

from alembic import op

revision = "20260613_0013"
down_revision = "20260606_0012"
branch_labels = None
depends_on = None


API_OWNER_CHECK = "owner_id = current_setting('app.current_user_id', true)::uuid"


def upgrade() -> None:
    op.execute("GRANT DELETE ON TABLE public.push_tokens TO mentioned_api")
    op.execute(
        f"""
        CREATE POLICY push_tokens_api_owner_delete ON public.push_tokens
          FOR DELETE
          TO mentioned_api
          USING ({API_OWNER_CHECK})
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS push_tokens_api_owner_delete ON public.push_tokens")
    op.execute("REVOKE DELETE ON TABLE public.push_tokens FROM mentioned_api")
