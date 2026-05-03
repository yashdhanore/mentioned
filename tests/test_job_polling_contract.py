from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.auth import Caller
from app.config import Settings
from app.models import JOB_STATUSES, Job, utc_now
from app.schemas.results import JobResultResponse
from app.services.job_coordinator import JobCoordinator, JobFailure
from extractor.types import PipelineResult, TextExtractionResult


PUBLIC_JOB_STATUSES = ("queued", "running", "succeeded", "partial", "failed", "canceled", "expired")


def _engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url="sqlite://",
        data_dir=tmp_path,
        max_job_create_burst_per_minute=100,
        max_jobs_created_per_day=100,
        max_active_jobs_per_user=100,
        worker_retry_base_delay_seconds=0,
        worker_stale_timeout_seconds=5,
    )


def _caller(user_id: str = "00000000-0000-4000-8000-000000000111") -> Caller:
    return Caller(subject_id=user_id, role="user")


def _pipeline_result(
    *,
    final_status: str = "succeeded",
    error_code: str | None = None,
    merged_text: str = "Useful extracted text",
) -> PipelineResult:
    return PipelineResult(
        source_kind="instagram_reel",
        final_status=final_status,
        error_code=error_code,
        error_message=None if error_code is None else "Internal failure detail",
        stage_runs=[],
        artifacts=[],
        text_result=TextExtractionResult(
            caption_text=None,
            spoken_text=None,
            visual_text=merged_text or None,
            image_text=None,
            merged_text=merged_text,
            warnings=[] if merged_text else ["No useful text could be extracted from the source."],
            debug={},
        ),
        candidate_mentions=[],
    )


def _create_job(coordinator: JobCoordinator):
    return coordinator.create_job(_caller(), "https://www.instagram.com/reel/abc/", None)


def _claim_job(coordinator: JobCoordinator, job_id: str) -> Job:
    claimed = coordinator.claim_next_job("worker-a")
    assert claimed is not None
    assert claimed.id == job_id
    return claimed


def test_public_status_tuple_is_stable() -> None:
    assert JOB_STATUSES == PUBLIC_JOB_STATUSES


def test_created_and_claimed_jobs_have_no_public_error_code(tmp_path: Path) -> None:
    engine = _engine()
    with Session(engine) as session:
        coordinator = JobCoordinator(session, _settings(tmp_path))
        created = _create_job(coordinator)

        assert created.status == "queued"
        assert created.error_code is None

        row = session.get(Job, created.job_id)
        assert row is not None
        row.error_code = "asr_failed"
        row.error_message = "ASR provider exploded"
        session.add(row)
        session.commit()

        queued_response = coordinator.get_job(_caller(), created.job_id)
        assert queued_response.status == "queued"
        assert queued_response.error_code is None
        assert queued_response.error_message is None

        _claim_job(coordinator, created.job_id)
        running_response = coordinator.get_job(_caller(), created.job_id)
        assert running_response.status == "running"
        assert running_response.error_code is None
        assert running_response.error_message is None


def test_retry_requeue_and_rerun_clear_public_error_code(tmp_path: Path) -> None:
    engine = _engine()
    with Session(engine) as session:
        coordinator = JobCoordinator(session, _settings(tmp_path))
        created = _create_job(coordinator)
        claimed = _claim_job(coordinator, created.job_id)

        coordinator.fail_claimed_job(
            claimed.id,
            JobFailure(error_code="asr_failed", error_message="failed", internal_error="stack", retryable=True),
        )
        retried_response = coordinator.get_job(_caller(), created.job_id)
        assert retried_response.status == "queued"
        assert retried_response.error_code is None
        assert retried_response.error_message is None

        retried = _claim_job(coordinator, created.job_id)
        coordinator.record_pipeline_result(retried.id, _pipeline_result())
        completed_response = coordinator.get_job(_caller(), created.job_id)
        assert completed_response.status == "succeeded"
        assert completed_response.error_code is None

        rerun_response = coordinator.rerun_job(_caller(), created.job_id)
        assert rerun_response.status == "queued"
        assert rerun_response.error_code is None


@pytest.mark.parametrize("final_status", ["succeeded", "partial"])
def test_usable_result_statuses_have_no_public_error_code(tmp_path: Path, final_status: str) -> None:
    engine = _engine()
    with Session(engine) as session:
        coordinator = JobCoordinator(session, _settings(tmp_path))
        created = _create_job(coordinator)
        claimed = _claim_job(coordinator, created.job_id)

        coordinator.record_pipeline_result(claimed.id, _pipeline_result(final_status=final_status))

        response = coordinator.get_job(_caller(), created.job_id)
        assert response.status == final_status
        assert response.error_code is None
        assert response.error_message is None


def test_no_text_result_uses_public_no_text_error_code(tmp_path: Path) -> None:
    engine = _engine()
    with Session(engine) as session:
        coordinator = JobCoordinator(session, _settings(tmp_path))
        created = _create_job(coordinator)
        claimed = _claim_job(coordinator, created.job_id)

        coordinator.record_pipeline_result(
            claimed.id,
            _pipeline_result(final_status="failed", error_code="no_text", merged_text=""),
        )

        response = coordinator.get_job(_caller(), created.job_id)
        assert response.status == "failed"
        assert response.error_code == "no_text_extracted"


def test_internal_terminal_failure_maps_to_pipeline_error(tmp_path: Path) -> None:
    engine = _engine()
    with Session(engine) as session:
        coordinator = JobCoordinator(session, _settings(tmp_path))
        created = _create_job(coordinator)
        claimed = _claim_job(coordinator, created.job_id)

        coordinator.fail_claimed_job(
            claimed.id,
            JobFailure(error_code="visual_reconstruction_failed", error_message="provider raw error", retryable=False),
        )

        response = coordinator.get_job(_caller(), created.job_id)
        assert response.status == "failed"
        assert response.error_code == "pipeline_error"
        assert response.error_message == "The extraction failed."


@pytest.mark.parametrize("final_status", ["queued", "running", "unknown"])
def test_pipeline_finalization_cannot_persist_non_terminal_statuses(tmp_path: Path, final_status: str) -> None:
    engine = _engine()
    with Session(engine) as session:
        coordinator = JobCoordinator(session, _settings(tmp_path))
        created = _create_job(coordinator)
        claimed = _claim_job(coordinator, created.job_id)

        coordinator.record_pipeline_result(claimed.id, _pipeline_result(final_status=final_status))

        response = coordinator.get_job(_caller(), created.job_id)
        assert response.status == "failed"
        assert response.error_code == "pipeline_error"


def test_cancellation_contract_for_queued_and_running_jobs(tmp_path: Path) -> None:
    engine = _engine()
    with Session(engine) as session:
        coordinator = JobCoordinator(session, _settings(tmp_path))
        queued = _create_job(coordinator)

        queued_cancel = coordinator.cancel_job(_caller(), queued.job_id)
        assert queued_cancel.status == "canceled"
        assert queued_cancel.error_code == "job_canceled"

        running = coordinator.create_job(_caller(), "https://www.instagram.com/reel/def/", None)
        _claim_job(coordinator, running.job_id)
        running_cancel = coordinator.cancel_job(_caller(), running.job_id)
        assert running_cancel.status == "running"
        assert running_cancel.error_code is None

        assert coordinator.cancel_if_requested(running.job_id, "worker-b") is False
        assert coordinator.cancel_if_requested(running.job_id, "worker-a") is True

        canceled = coordinator.get_job(_caller(), running.job_id)
        assert canceled.status == "canceled"
        assert canceled.error_code == "job_canceled"


def test_expired_job_uses_public_expired_error_code(tmp_path: Path) -> None:
    engine = _engine()
    with Session(engine) as session:
        coordinator = JobCoordinator(session, _settings(tmp_path))
        created = _create_job(coordinator)
        _claim_job(coordinator, created.job_id)

        row = session.get(Job, created.job_id)
        assert row is not None
        row.heartbeat_at = utc_now() - timedelta(seconds=10)
        row.attempt_count = row.max_attempts
        session.add(row)
        session.commit()

        assert coordinator.recover_stale_jobs() == 1
        response = coordinator.get_job(_caller(), created.job_id)
        assert response.status == "expired"
        assert response.error_code == "job_expired"


def test_result_response_has_no_job_level_error_code() -> None:
    assert "error_code" not in JobResultResponse.model_fields
