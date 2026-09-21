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


def _insert_saved_source(
    connection, *, saved_source_id: str, source_id: str, owner_id: str, canonical_url: str
) -> None:
    connection.execute(
        text(
            """
            insert into public.sources
              (id, source_key, platform, source_type, external_id, canonical_url)
            values
              (:source_id, :source_key, 'instagram', 'reel', :external_id, :canonical_url)
            """
        ),
        {
            "source_id": source_id,
            # Bound separately from :source_id (same string value, different column
            # type: uuid vs text) - psycopg's extended query protocol infers one type
            # per parameter name across the whole statement, so reusing :source_id
            # here raises "inconsistent types deduced for parameter" against a real
            # Postgres server.
            "external_id": source_id,
            "source_key": f"instagram:reel:{source_id}",
            "canonical_url": canonical_url,
        },
    )
    connection.execute(
        text(
            """
            insert into public.saved_sources (id, owner_id, source_id)
            values (:saved_source_id, :owner_id, :source_id)
            """
        ),
        {"saved_source_id": saved_source_id, "owner_id": owner_id, "source_id": source_id},
    )


def _delete_saved_sources_and_sources(connection, source_ids: list[str]) -> None:
    for source_id in source_ids:
        connection.execute(
            text("delete from public.saved_sources where source_id = :source_id"),
            {"source_id": source_id},
        )
        connection.execute(
            text("delete from public.sources where id = :source_id"), {"source_id": source_id}
        )


def _uuid_strings(values) -> list[str]:
    return [str(value) for value in values]


def test_api_and_worker_roles_do_not_bypass_rls(api_engine, worker_engine) -> None:
    for row in (_role_flags(api_engine), _role_flags(worker_engine)):
        assert row["rolsuper"] is False
        assert row["rolbypassrls"] is False


def test_api_role_requires_and_honors_rls_context(admin_engine, api_engine) -> None:
    user_a = str(uuid4())
    user_b = str(uuid4())
    source_a = str(uuid4())
    source_b = str(uuid4())
    saved_a = str(uuid4())
    saved_b = str(uuid4())
    source_ids = [source_a, source_b]

    with admin_engine.begin() as connection:
        _insert_saved_source(
            connection,
            saved_source_id=saved_a,
            source_id=source_a,
            owner_id=user_a,
            canonical_url="https://www.instagram.com/reel/APIA/",
        )
        _insert_saved_source(
            connection,
            saved_source_id=saved_b,
            source_id=source_b,
            owner_id=user_b,
            canonical_url="https://www.instagram.com/reel/APIB/",
        )

    try:
        with api_engine.begin() as connection:
            rows = (
                connection.execute(
                    text(
                        "select id from public.saved_sources where id in (:saved_a, :saved_b) "
                        "order by id"
                    ),
                    {"saved_a": saved_a, "saved_b": saved_b},
                )
                .scalars()
                .all()
            )
            assert rows == []

        with api_engine.begin() as connection:
            connection.execute(
                text("select set_config('app.current_user_id', :owner_id, true)"),
                {"owner_id": user_a},
            )
            rows = (
                connection.execute(
                    text(
                        "select id from public.saved_sources where id in (:saved_a, :saved_b) "
                        "order by id"
                    ),
                    {"saved_a": saved_a, "saved_b": saved_b},
                )
                .scalars()
                .all()
            )
            assert _uuid_strings(rows) == [saved_a]
    finally:
        with admin_engine.begin() as connection:
            _delete_saved_sources_and_sources(connection, source_ids)


def test_worker_role_can_process_without_user_rls_context(admin_engine, worker_engine) -> None:
    owner_id = str(uuid4())
    source_id = str(uuid4())
    item_id = str(uuid4())

    with admin_engine.begin() as connection:
        _insert_saved_source(
            connection,
            saved_source_id=str(uuid4()),
            source_id=source_id,
            owner_id=owner_id,
            canonical_url="https://www.instagram.com/reel/WORKER/",
        )

    try:
        with worker_engine.begin() as connection:
            updated_source_id = connection.execute(
                text(
                    """
                    update public.sources
                    set status = 'processing', processing_started_at = now()
                    where id = :source_id
                    returning id
                    """
                ),
                {"source_id": source_id},
            ).scalar_one()
            assert str(updated_source_id) == source_id

            connection.execute(
                text(
                    """
                    insert into public.source_items (id, source_id, category, title)
                    values (:item_id, :source_id, 'book', 'RLS Proof')
                    """
                ),
                {
                    "item_id": item_id,
                    "source_id": source_id,
                },
            )
    finally:
        with admin_engine.begin() as connection:
            _delete_saved_sources_and_sources(connection, [source_id])


def test_anon_and_authenticated_roles_cannot_read_tables(admin_engine) -> None:
    for role_name in ("anon", "authenticated"):
        try:
            with admin_engine.begin() as connection:
                connection.execute(text(f"set local role {role_name}"))
                with pytest.raises(DBAPIError):
                    connection.execute(text("select count(*) from public.sources")).scalar_one()
        except DBAPIError as exc:
            if "permission denied to set role" in str(exc).casefold():
                pytest.skip(f"Admin test role cannot SET ROLE {role_name}")
            raise
