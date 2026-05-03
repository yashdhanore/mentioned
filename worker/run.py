from __future__ import annotations

import argparse
import time

from sqlmodel import Session

from app.config import get_settings
from app.db import create_db_and_tables, engine
from app.services.job_coordinator import JobCoordinator, JobFailure
from extractor.pipeline import run_pipeline
from extractor.stages.normalize_url import SourceUrlError


def process_job(job_id: str, source_url: str, worker_id: str) -> None:
    with Session(engine) as session:
        coordinator = JobCoordinator(session)
        coordinator.heartbeat(job_id, worker_id, current_stage="pipeline", progress=0.1)
        if coordinator.cancel_if_requested(job_id, worker_id):
            return

    try:
        result = run_pipeline(job_id, source_url)
    except SourceUrlError as exc:
        with Session(engine) as session:
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
        with Session(engine) as session:
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

    with Session(engine) as session:
        coordinator = JobCoordinator(session)
        if coordinator.cancel_if_requested(job_id, worker_id):
            return
        coordinator.record_pipeline_result(job_id, result)


def run_worker(*, once: bool) -> None:
    settings = get_settings()
    create_db_and_tables()
    while True:
        with Session(engine) as session:
            coordinator = JobCoordinator(session)
            coordinator.recover_stale_jobs()
            job = coordinator.claim_next_job(settings.worker_id)
        if job is None:
            if once:
                return
            time.sleep(settings.worker_poll_interval_seconds)
            continue
        process_job(job.id, job.source_url, settings.worker_id)
        if once:
            return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Process at most one queued job.")
    args = parser.parse_args()
    run_worker(once=args.once)


if __name__ == "__main__":
    main()
