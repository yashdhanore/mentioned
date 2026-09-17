"""dedicated worker role with explicit rls policies

Revision ID: 20260505_0004
Revises: 20260504_0003
Create Date: 2026-05-05
"""

from __future__ import annotations

from alembic import op

revision = "20260505_0004"
down_revision = "20260504_0003"
branch_labels = None
depends_on = None


API_OWNER_CHECK = "owner_id = current_setting('app.current_user_id', true)::uuid"


def upgrade() -> None:
    op.execute("REVOKE ALL ON TABLE public.jobs, public.mentions FROM anon, authenticated")

    op.execute("GRANT USAGE ON SCHEMA public TO mentioned_api, mentioned_worker")
    op.execute("GRANT SELECT, INSERT ON TABLE public.jobs TO mentioned_api")
    op.execute("GRANT SELECT, UPDATE ON TABLE public.mentions TO mentioned_api")
    op.execute("GRANT SELECT, UPDATE ON TABLE public.jobs TO mentioned_worker")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE public.mentions TO mentioned_worker")

    op.execute("DROP POLICY IF EXISTS jobs_owner_policy ON public.jobs")
    op.execute("DROP POLICY IF EXISTS mentions_owner_policy ON public.mentions")

    op.execute(
        f"""
        CREATE POLICY jobs_api_owner_select ON public.jobs
          FOR SELECT
          TO mentioned_api
          USING ({API_OWNER_CHECK})
        """
    )
    op.execute(
        f"""
        CREATE POLICY jobs_api_owner_insert ON public.jobs
          FOR INSERT
          TO mentioned_api
          WITH CHECK ({API_OWNER_CHECK})
        """
    )
    op.execute(
        f"""
        CREATE POLICY mentions_api_owner_select ON public.mentions
          FOR SELECT
          TO mentioned_api
          USING ({API_OWNER_CHECK})
        """
    )
    op.execute(
        f"""
        CREATE POLICY mentions_api_owner_update ON public.mentions
          FOR UPDATE
          TO mentioned_api
          USING ({API_OWNER_CHECK})
          WITH CHECK ({API_OWNER_CHECK})
        """
    )

    op.execute(
        """
        CREATE POLICY jobs_worker_all ON public.jobs
          FOR ALL
          TO mentioned_worker
          USING (true)
          WITH CHECK (true)
        """
    )
    op.execute(
        """
        CREATE POLICY mentions_worker_all ON public.mentions
          FOR ALL
          TO mentioned_worker
          USING (true)
          WITH CHECK (true)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS mentions_worker_all ON public.mentions")
    op.execute("DROP POLICY IF EXISTS jobs_worker_all ON public.jobs")
    op.execute("DROP POLICY IF EXISTS mentions_api_owner_update ON public.mentions")
    op.execute("DROP POLICY IF EXISTS mentions_api_owner_select ON public.mentions")
    op.execute("DROP POLICY IF EXISTS jobs_api_owner_insert ON public.jobs")
    op.execute("DROP POLICY IF EXISTS jobs_api_owner_select ON public.jobs")

    op.execute(
        "REVOKE ALL ON TABLE public.jobs, public.mentions FROM mentioned_api, mentioned_worker"
    )

    op.execute(
        """
        CREATE POLICY jobs_owner_policy ON public.jobs
          FOR ALL
          USING (owner_id = current_setting('app.current_user_id')::uuid)
          WITH CHECK (owner_id = current_setting('app.current_user_id')::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY mentions_owner_policy ON public.mentions
          FOR ALL
          USING (owner_id = current_setting('app.current_user_id')::uuid)
          WITH CHECK (owner_id = current_setting('app.current_user_id')::uuid)
        """
    )
