from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from src.database import create_sql_engine


ADMIN_DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
API_DATABASE_URL = os.getenv("POSTGRES_TEST_API_DATABASE_URL")
WORKER_DATABASE_URL = os.getenv("POSTGRES_TEST_WORKER_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not (ADMIN_DATABASE_URL and API_DATABASE_URL and WORKER_DATABASE_URL),
    reason=(
        "Set POSTGRES_TEST_DATABASE_URL, POSTGRES_TEST_API_DATABASE_URL, "
        "and POSTGRES_TEST_WORKER_DATABASE_URL to run dedicated-role RLS proofs"
    ),
)


@pytest.fixture
def admin_engine():
    engine = create_sql_engine(ADMIN_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def api_engine():
    engine = create_sql_engine(API_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def worker_engine():
    engine = create_sql_engine(WORKER_DATABASE_URL)
    yield engine
    engine.dispose()


def _role_flags(engine) -> dict[str, object]:
    with engine.connect() as connection:
        return dict(
            connection.execute(
                text(
                    """
                    select current_user, rolsuper, rolbypassrls
                    from pg_roles
                    where rolname = current_user
                    """
                )
            )
            .mappings()
            .one()
        )


def _insert_job(connection, *, job_id: str, owner_id: str, source_url: str) -> None:
    connection.execute(
        text(
            """
            insert into public.jobs (id, owner_id, source_url, status)
            values (:job_id, :owner_id, :source_url, 'pending')
            """
        ),
        {"job_id": job_id, "owner_id": owner_id, "source_url": source_url},
    )


def _delete_jobs(connection, job_ids: list[str]) -> None:
    for job_id in job_ids:
        connection.execute(text("delete from public.jobs where id = :job_id"), {"job_id": job_id})


def _uuid_strings(values) -> list[str]:
    return [str(value) for value in values]


def test_api_and_worker_roles_do_not_bypass_rls(api_engine, worker_engine) -> None:
    for row in (_role_flags(api_engine), _role_flags(worker_engine)):
        assert row["rolsuper"] is False
        assert row["rolbypassrls"] is False


def test_api_role_requires_and_honors_rls_context(admin_engine, api_engine) -> None:
    user_a = str(uuid4())
    user_b = str(uuid4())
    job_a = str(uuid4())
    job_b = str(uuid4())
    job_ids = [job_a, job_b]

    with admin_engine.begin() as connection:
        _insert_job(
            connection,
            job_id=job_a,
            owner_id=user_a,
            source_url="https://www.instagram.com/reel/APIA/",
        )
        _insert_job(
            connection,
            job_id=job_b,
            owner_id=user_b,
            source_url="https://www.instagram.com/reel/APIB/",
        )

    try:
        with api_engine.begin() as connection:
            rows = connection.execute(
                text("select id from public.jobs where id in (:job_a, :job_b) order by id"),
                {"job_a": job_a, "job_b": job_b},
            ).scalars().all()
            assert rows == []

        with api_engine.begin() as connection:
            connection.execute(
                text("select set_config('app.current_user_id', :owner_id, true)"),
                {"owner_id": user_a},
            )
            rows = connection.execute(
                text("select id from public.jobs where id in (:job_a, :job_b) order by id"),
                {"job_a": job_a, "job_b": job_b},
            ).scalars().all()
            assert _uuid_strings(rows) == [job_a]
    finally:
        with admin_engine.begin() as connection:
            _delete_jobs(connection, job_ids)


def test_worker_role_can_process_without_user_rls_context(admin_engine, worker_engine) -> None:
    owner_id = str(uuid4())
    job_id = str(uuid4())
    mention_id = str(uuid4())

    with admin_engine.begin() as connection:
        _insert_job(
            connection,
            job_id=job_id,
            owner_id=owner_id,
            source_url="https://www.instagram.com/reel/WORKER/",
        )

    try:
        with worker_engine.begin() as connection:
            updated_job_id = connection.execute(
                text(
                    """
                    update public.jobs
                    set locked_by = 'worker-proof', locked_at = now(), heartbeat_at = now()
                    where id = :job_id
                    returning id
                    """
                ),
                {"job_id": job_id},
            ).scalar_one()
            assert str(updated_job_id) == job_id

            connection.execute(
                text(
                    """
                    insert into public.mentions
                      (id, owner_id, job_id, title, category, source_url)
                    values
                      (:mention_id, :owner_id, :job_id, 'RLS Proof', 'book',
                       'https://www.instagram.com/reel/WORKER/')
                    """
                ),
                {
                    "mention_id": mention_id,
                    "owner_id": owner_id,
                    "job_id": job_id,
                },
            )
    finally:
        with admin_engine.begin() as connection:
            _delete_jobs(connection, [job_id])


def test_anon_and_authenticated_roles_cannot_read_tables(admin_engine) -> None:
    for role_name in ("anon", "authenticated"):
        try:
            with admin_engine.begin() as connection:
                connection.execute(text(f"set local role {role_name}"))
                with pytest.raises(DBAPIError):
                    connection.execute(text("select count(*) from public.jobs")).scalar_one()
        except DBAPIError as exc:
            if "permission denied to set role" in str(exc).casefold():
                pytest.skip(f"Admin test role cannot SET ROLE {role_name}")
            raise
