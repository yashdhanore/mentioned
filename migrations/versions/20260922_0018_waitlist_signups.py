"""add waitlist_signups

Revision ID: 20260922_0018
Revises: 20260921_0017
Create Date: 2026-09-22

waitlist_signups previously existed only via
supabase/migrations/20260608214109_create_waitlist_signups.sql, so a database built
from `alembic upgrade head` alone had no table behind POST /v1/waitlist. Production
already has the table from that Supabase migration, so this creates it with
IF NOT EXISTS/IF EXISTS guards throughout and is safe to run on either a fresh
database or production. It also replaces the original policy (`for all using (true)`
with no `to <role>`, so it applied to every role) with one scoped to mentioned_api.
"""

from __future__ import annotations

from alembic import op

revision = "20260922_0018"
down_revision = "20260921_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.waitlist_signups (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            email text NOT NULL,
            source text,
            user_agent text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT waitlist_signups_email_normalized CHECK (email = lower(trim(email))),
            CONSTRAINT waitlist_signups_email_not_blank CHECK (length(email) > 3),
            CONSTRAINT waitlist_signups_source_length
                CHECK (source IS NULL OR length(source) <= 120)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS waitlist_signups_email_lower_idx "
        "ON public.waitlist_signups (lower(email))"
    )
    op.execute("ALTER TABLE public.waitlist_signups ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON TABLE public.waitlist_signups FROM anon, authenticated")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE public.waitlist_signups TO mentioned_api")

    op.execute("DROP POLICY IF EXISTS waitlist_signups_app_manage ON public.waitlist_signups")
    op.execute("DROP POLICY IF EXISTS waitlist_signups_api_manage ON public.waitlist_signups")
    op.execute(
        """
        CREATE POLICY waitlist_signups_api_manage ON public.waitlist_signups
          FOR ALL
          TO mentioned_api
          USING (true)
          WITH CHECK (true)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS waitlist_signups_api_manage ON public.waitlist_signups")
    op.execute("REVOKE ALL ON TABLE public.waitlist_signups FROM mentioned_api")
    op.execute("DROP INDEX IF EXISTS public.waitlist_signups_email_lower_idx")
    op.execute("DROP TABLE IF EXISTS public.waitlist_signups")
