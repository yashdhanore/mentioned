"""allow api hard delete of saved posts

Revision ID: 20260606_0012
Revises: 20260606_0011
Create Date: 2026-06-06
"""

from __future__ import annotations

from alembic import op


revision = "20260606_0012"
down_revision = "20260606_0011"
branch_labels = None
depends_on = None


API_OWNER_CHECK = "owner_id = current_setting('app.current_user_id', true)::uuid"


def upgrade() -> None:
    op.execute("GRANT DELETE ON TABLE public.jobs, public.mentions TO mentioned_api")
    op.execute("GRANT SELECT, DELETE ON TABLE public.job_events TO mentioned_api")

    op.execute(
        f"""
        CREATE POLICY jobs_api_owner_delete ON public.jobs
          FOR DELETE
          TO mentioned_api
          USING ({API_OWNER_CHECK})
        """
    )
    op.execute(
        f"""
        CREATE POLICY mentions_api_owner_delete ON public.mentions
          FOR DELETE
          TO mentioned_api
          USING ({API_OWNER_CHECK})
        """
    )
    op.execute(
        f"""
        CREATE POLICY job_events_api_owner_select ON public.job_events
          FOR SELECT
          TO mentioned_api
          USING ({API_OWNER_CHECK})
        """
    )
    op.execute(
        f"""
        CREATE POLICY job_events_api_owner_delete ON public.job_events
          FOR DELETE
          TO mentioned_api
          USING ({API_OWNER_CHECK})
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS job_events_api_owner_delete ON public.job_events")
    op.execute("DROP POLICY IF EXISTS job_events_api_owner_select ON public.job_events")
    op.execute("DROP POLICY IF EXISTS mentions_api_owner_delete ON public.mentions")
    op.execute("DROP POLICY IF EXISTS jobs_api_owner_delete ON public.jobs")

    op.execute("REVOKE SELECT, DELETE ON TABLE public.job_events FROM mentioned_api")
    op.execute("REVOKE DELETE ON TABLE public.jobs, public.mentions FROM mentioned_api")
