from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, delete, select

from app.models import Artifact, BookCandidate, Job, StageRun, TextResult
from app.schemas.jobs import JobResponse
from app.schemas.results import (
    ArtifactResponse,
    JobResultResponse,
    StageRunResponse,
    TextResultResponse,
)
from extractor.stages.normalize_url import detect_source_kind, normalize_input_url
from extractor.types import ArtifactRecord, ExtractedBookCandidate, StageOutcome, TextExtractionResult


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def serialize_json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=True)


def parse_json(value: str | None) -> Any:
    if value is None:
        return None
    return json.loads(value)


def to_job_response(job: Job) -> JobResponse:
    return JobResponse(
        job_id=job.id,
        source_url=job.source_url,
        source_kind=job.source_kind,
        status=job.status,
        current_stage=job.current_stage,
        progress=job.progress,
        error_code=job.error_code,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def create_job(session: Session, source_url: str) -> Job:
    normalized_url = normalize_input_url(source_url)
    job = Job(
        source_url=normalized_url,
        source_kind=detect_source_kind(normalized_url),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def get_job(session: Session, job_id: str) -> Job | None:
    return session.get(Job, job_id)


def claim_next_queued_job(session: Session) -> Job | None:
    statement = select(Job).where(Job.status == "queued").order_by(Job.created_at)
    job = session.exec(statement).first()
    if job is None:
        return None
    job.status = "running"
    job.current_stage = "claimed"
    job.progress = 0.01
    job.error_code = None
    job.error_message = None
    job.updated_at = utc_now()
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def rerun_job(session: Session, job: Job) -> Job:
    job.status = "queued"
    job.current_stage = None
    job.progress = 0.0
    job.error_code = None
    job.error_message = None
    job.updated_at = utc_now()
    session.add(job)
    session.exec(delete(Artifact).where(Artifact.job_id == job.id))
    session.exec(delete(StageRun).where(StageRun.job_id == job.id))
    session.exec(delete(TextResult).where(TextResult.job_id == job.id))
    session.exec(delete(BookCandidate).where(BookCandidate.job_id == job.id))
    session.commit()
    session.refresh(job)
    return job


def update_job_stage(
    session: Session,
    job: Job,
    *,
    current_stage: str,
    progress: float,
) -> Job:
    job.current_stage = current_stage
    job.progress = progress
    job.updated_at = utc_now()
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def mark_job_failed(session: Session, job: Job, *, error_code: str, error_message: str) -> Job:
    job.status = "failed"
    job.current_stage = "failed"
    job.error_code = error_code
    job.error_message = error_message
    job.updated_at = utc_now()
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def mark_job_completed(
    session: Session,
    job: Job,
    *,
    source_kind: str,
    status: str,
    error_code: str | None = None,
    error_message: str | None = None,
) -> Job:
    job.status = status
    job.source_kind = source_kind
    job.current_stage = "completed" if status in {"succeeded", "partial"} else "failed"
    job.progress = 1.0
    job.error_code = error_code
    job.error_message = error_message
    job.updated_at = utc_now()
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def append_stage_run(session: Session, job_id: str, stage_run: StageOutcome) -> StageRun:
    row = StageRun(
        job_id=job_id,
        stage=stage_run.stage,
        success=stage_run.success,
        duration_ms=stage_run.duration_ms,
        payload_json=serialize_json(stage_run.payload),
        error_text=stage_run.error_text,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def record_artifact(session: Session, job_id: str, artifact: ArtifactRecord) -> Artifact:
    row = Artifact(
        job_id=job_id,
        kind=artifact.kind,
        path=artifact.path,
        metadata_json=serialize_json(artifact.metadata),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def replace_candidates(
    session: Session,
    job_id: str,
    candidates: list[ExtractedBookCandidate],
) -> None:
    session.exec(delete(BookCandidate).where(BookCandidate.job_id == job_id))
    for candidate in candidates:
        session.add(
            BookCandidate(
                job_id=job_id,
                title=candidate.title,
                author=candidate.author,
                confidence=candidate.confidence,
                evidence_json=serialize_json(candidate.evidence),
                canonical_source=candidate.canonical_source,
                canonical_id=candidate.canonical_id,
                canonical_title=candidate.canonical_title,
                canonical_author=candidate.canonical_author,
            )
        )
    session.commit()


def replace_text_result(
    session: Session,
    job_id: str,
    text_result: TextExtractionResult,
) -> None:
    session.exec(delete(TextResult).where(TextResult.job_id == job_id))
    now = utc_now()
    session.add(
        TextResult(
            job_id=job_id,
            caption_text=text_result.caption_text,
            spoken_text=text_result.spoken_text,
            visual_text=text_result.visual_text,
            image_text=text_result.image_text,
            merged_text=text_result.merged_text,
            warnings_json=serialize_json(text_result.warnings),
            debug_json=serialize_json(text_result.debug),
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()


def _empty_text_response() -> TextResultResponse:
    warnings = ["Text result has not been written yet."]
    return TextResultResponse(
        caption_text=None,
        spoken_text=None,
        visual_text=None,
        image_text=None,
        merged_text="",
        warnings=warnings,
        debug=None,
    )


def build_job_result(session: Session, job: Job) -> JobResultResponse:
    text_row = session.exec(select(TextResult).where(TextResult.job_id == job.id)).first()
    artifact_rows = session.exec(
        select(Artifact).where(Artifact.job_id == job.id).order_by(Artifact.created_at)
    ).all()
    stage_rows = session.exec(
        select(StageRun).where(StageRun.job_id == job.id).order_by(StageRun.created_at)
    ).all()
    return JobResultResponse(
        job_id=job.id,
        source_url=job.source_url,
        source_kind=job.source_kind,
        status=job.status,
        current_stage=job.current_stage,
        progress=job.progress,
        text=(
            TextResultResponse(
                caption_text=text_row.caption_text,
                spoken_text=text_row.spoken_text,
                visual_text=text_row.visual_text,
                image_text=text_row.image_text,
                merged_text=text_row.merged_text,
                warnings=parse_json(text_row.warnings_json) or [],
                debug=parse_json(text_row.debug_json),
            )
            if text_row is not None
            else _empty_text_response()
        ),
        stage_runs=[
            StageRunResponse(
                stage=row.stage,
                success=row.success,
                duration_ms=row.duration_ms,
                payload=parse_json(row.payload_json),
                error_text=row.error_text,
                created_at=row.created_at,
            )
            for row in stage_rows
        ],
        artifacts=[
            ArtifactResponse(
                kind=row.kind,
                path=row.path,
                metadata=parse_json(row.metadata_json),
                created_at=row.created_at,
            )
            for row in artifact_rows
        ],
    )
