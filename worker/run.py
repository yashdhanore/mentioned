from __future__ import annotations

import argparse
import time

from sqlmodel import Session

from app.config import get_settings
from app.db import create_db_and_tables, engine
from app.services.job_service import (
    append_stage_run,
    claim_next_queued_job,
    get_job,
    mark_job_completed,
    mark_job_failed,
    record_artifact,
    replace_text_result,
    update_job_stage,
)
from extractor.pipeline import run_pipeline


def process_job(job_id: str) -> None:
    with Session(engine) as session:
        job = get_job(session, job_id)
        if job is None:
            return
        update_job_stage(session, job, current_stage="pipeline", progress=0.1)

    try:
        result = run_pipeline(job_id, job.source_url)
    except Exception as exc:
        with Session(engine) as session:
            job = get_job(session, job_id)
            if job is not None:
                mark_job_failed(
                    session,
                    job,
                    error_code="pipeline_error",
                    error_message=str(exc),
                )
        return

    with Session(engine) as session:
        job = get_job(session, job_id)
        if job is None:
            return
        for stage_run in result.stage_runs:
            append_stage_run(session, job_id, stage_run)
        for artifact in result.artifacts:
            record_artifact(session, job_id, artifact)
        replace_text_result(session, job_id, result.text_result)
        mark_job_completed(
            session,
            job,
            source_kind=result.source_kind,
            status=result.final_status,
            error_code=result.error_code,
            error_message=result.error_message,
        )


def run_worker(*, once: bool) -> None:
    settings = get_settings()
    create_db_and_tables()
    while True:
        with Session(engine) as session:
            job = claim_next_queued_job(session)
        if job is None:
            if once:
                return
            time.sleep(settings.worker_poll_interval_seconds)
            continue
        process_job(job.id)
        if once:
            return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Process at most one queued job.")
    args = parser.parse_args()
    run_worker(once=args.once)


if __name__ == "__main__":
    main()
