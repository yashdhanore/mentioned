from __future__ import annotations

import argparse
import time

from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.config import Settings, get_settings
from app.db import create_db_and_tables, create_sql_engine
from app.services.job_coordinator import JobCoordinator, JobFailure
from extractor.pipeline import run_pipeline
from extractor.stages.normalize_url import SourceUrlError


def _worker_database_url(settings: Settings) -> str:
    if settings.worker_database_url:
        return settings.worker_database_url
    if settings.is_production:
        raise RuntimeError("Production worker requires WORKER_DATABASE_URL")
    return settings.database_url


def process_job(job_id: str, source_url: str, worker_id: str, db_engine: Engine) -> None:
    with Session(db_engine) as session:
        coordinator = JobCoordinator(session)
        coordinator.heartbeat(job_id, worker_id, current_stage="pipeline", progress=0.1)
        if coordinator.cancel_if_requested(job_id, worker_id):
            return

    try:
        result = run_pipeline(job_id, source_url)
    except SourceUrlError as exc:
        with Session(db_engine) as session:
            coordinator = JobCoordinator(session)
            if coordinator.cancel_if_requested(job_id, worker_id):
                return
            coordinator.fail_claimed_job(
                job_id,
                JobFailure(
                    error_code=exc.error_code,
                    error_message=str(exc),
                    internal_error=str(exc),
                    retryable=False,
                ),
            )
        return
    except Exception as exc:
        with Session(db_engine) as session:
            coordinator = JobCoordinator(session)
            if coordinator.cancel_if_requested(job_id, worker_id):
                return
            coordinator.fail_claimed_job(
                job_id,
                JobFailure(
                    error_code="pipeline_error",
                    error_message="The extraction failed.",
                    internal_error=str(exc),
                    retryable=True,
                ),
            )
        return

    with Session(db_engine) as session:
        coordinator = JobCoordinator(session)
        if coordinator.cancel_if_requested(job_id, worker_id):
            return
        coordinator.record_pipeline_result(job_id, result)


def run_worker(*, once: bool) -> None:
    settings = get_settings()
    worker_engine = create_sql_engine(_worker_database_url(settings))
    try:
        create_db_and_tables(worker_engine)
        while True:
            with Session(worker_engine) as session:
                coordinator = JobCoordinator(session)
                coordinator.recover_stale_jobs()
                job = coordinator.claim_next_job(settings.worker_id)
            if job is None:
                if once:
                    return
                time.sleep(settings.worker_poll_interval_seconds)
                continue
            process_job(job.id, job.source_url, settings.worker_id, worker_engine)
            if once:
                return
    finally:
        worker_engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Process at most one queued job.")
    args = parser.parse_args()
    run_worker(once=args.once)


if __name__ == "__main__":
    main()
