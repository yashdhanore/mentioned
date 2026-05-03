from __future__ import annotations

"""
Run the real Postgres worker-claiming proof with:

    POSTGRES_TEST_DATABASE_URL=postgresql://... python -m pytest tests/test_postgres_worker_claiming.py
"""

from collections.abc import Iterator
from datetime import timedelta
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.auth import Caller
from app.config import Settings
from app.db import normalize_database_url
from app.models import Job, utc_now
from app.services.job_coordinator import JobCoordinator


POSTGRES_TEST_DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_DATABASE_URL,
    reason="POSTGRES_TEST_DATABASE_URL is required for the real Postgres worker claiming proof.",
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=POSTGRES_TEST_DATABASE_URL or "postgresql://unused",
        data_dir=tmp_path,
        max_job_create_burst_per_minute=100,
        max_jobs_created_per_day=100,
        max_active_jobs_per_user=100,
    )


@pytest.fixture()
def postgres_engine() -> Iterator[Engine]:
    assert POSTGRES_TEST_DATABASE_URL is not None
    database_url = normalize_database_url(POSTGRES_TEST_DATABASE_URL)
    schema_name = f"test_worker_claiming_{uuid4().hex}"
    admin_engine = create_engine(database_url, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f'create schema "{schema_name}"'))

    engine = create_engine(database_url, pool_pre_ping=True)

    @event.listens_for(engine, "connect")
    def _set_search_path(dbapi_connection, _connection_record) -> None:
        with dbapi_connection.cursor() as cursor:
            cursor.execute(f'set search_path to "{schema_name}"')

    SQLModel.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'drop schema if exists "{schema_name}" cascade'))
        admin_engine.dispose()


def _caller() -> Caller:
    return Caller(subject_id="00000000-0000-4000-8000-000000000111", role="user")


def _seed_ordered_jobs(engine: Engine, tmp_path: Path) -> tuple[str, str]:
    settings = _settings(tmp_path)
    now = utc_now()
    with Session(engine) as session:
        coordinator = JobCoordinator(session, settings)
        first = coordinator.create_job(_caller(), "https://www.instagram.com/reel/first/", None)
        second = coordinator.create_job(_caller(), "https://www.instagram.com/reel/second/", None)

        first_row = session.get(Job, first.job_id)
        second_row = session.get(Job, second.job_id)
        assert first_row is not None
        assert second_row is not None

        first_row.priority = 10
        first_row.created_at = now - timedelta(seconds=2)
        first_row.updated_at = first_row.created_at
        first_row.next_run_at = first_row.created_at
        second_row.priority = 0
        second_row.created_at = now - timedelta(seconds=1)
        second_row.updated_at = second_row.created_at
        second_row.next_run_at = second_row.created_at
        session.add(first_row)
        session.add(second_row)
        session.commit()
        return first.job_id, second.job_id


def _assert_claimed_state(engine: Engine, job_id: str, worker_id: str) -> None:
    with Session(engine) as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.status == "running"
        assert job.locked_by == worker_id
        assert job.locked_at is not None
        assert job.heartbeat_at is not None
        assert job.attempt_count == 1
        assert job.current_stage == "claimed"
        assert job.progress == pytest.approx(0.01)


def test_claim_next_job_skips_locked_first_job_on_postgres(postgres_engine: Engine, tmp_path) -> None:
    first_job_id, second_job_id = _seed_ordered_jobs(postgres_engine, tmp_path)
    settings = _settings(tmp_path)

    lock_connection = postgres_engine.connect()
    lock_transaction = lock_connection.begin()
    try:
        locked = lock_connection.execute(
            text("select id from jobs where id = :job_id for update"),
            {"job_id": first_job_id},
        ).one()
        assert str(locked.id) == first_job_id

        with Session(postgres_engine) as claim_session:
            claim_session.execute(text("set local statement_timeout = '1000ms'"))
            claimed_by_worker_b = JobCoordinator(claim_session, settings).claim_next_job("worker-b")

        assert claimed_by_worker_b is not None
        assert claimed_by_worker_b.id == second_job_id
        _assert_claimed_state(postgres_engine, second_job_id, "worker-b")

        with Session(postgres_engine) as session:
            first_job = session.get(Job, first_job_id)
            assert first_job is not None
            assert first_job.status == "queued"
            assert first_job.locked_by is None
            assert first_job.attempt_count == 0
    finally:
        lock_transaction.rollback()
        lock_connection.close()

    with Session(postgres_engine) as claim_session:
        claimed_by_worker_a = JobCoordinator(claim_session, settings).claim_next_job("worker-a")

    assert claimed_by_worker_a is not None
    assert claimed_by_worker_a.id == first_job_id
    assert {claimed_by_worker_a.id, claimed_by_worker_b.id} == {first_job_id, second_job_id}
    _assert_claimed_state(postgres_engine, first_job_id, "worker-a")
