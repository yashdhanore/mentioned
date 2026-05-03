from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any

from sqlalchemy import and_, func, or_, text
from sqlmodel import Session, delete, select

from app.auth import Caller
from app.config import Settings, get_settings
from app.models import (
    MENTION_CATEGORIES,
    Artifact,
    Job,
    ProviderCall,
    SavedMention,
    StageRun,
    TextResult,
    utc_now,
)
from app.schemas.jobs import JobLinks, JobListResponse, JobResponse
from app.schemas.mentions import SavedMentionListResponse, SavedMentionResponse
from app.schemas.results import ArtifactResponse, JobResultResponse, StageRunResponse, TextResultResponse
from app.services.artifact_store import LocalArtifactStore
from extractor.stages.normalize_url import SourceUrlError, normalize_supported_source_url
from extractor.types import ExtractedMentionCandidate, PipelineResult, StageOutcome, TextExtractionResult


TERMINAL_STATUSES = {"succeeded", "partial", "failed", "canceled", "expired"}
ACTIVE_STATUSES = {"queued", "running"}
USABLE_RESULT_STATUSES = {"succeeded", "partial"}
PIPELINE_TERMINAL_STATUSES = {"succeeded", "partial", "failed"}
MIN_AUTO_SAVE_CONFIDENCE = 0.6
RETRYABLE_ERROR_CODES = {
    "pipeline_error",
    "source_fetch_failed",
    "source_probe_failed",
    "source_download_failed",
    "media_processing_failed",
    "asr_failed",
    "ocr_failed",
    "visual_reconstruction_failed",
}
PUBLIC_ERROR_MESSAGES = {
    "invalid_source_url": "The source URL is not valid.",
    "unsupported_source_kind": "Only public Instagram Reels and posts are supported.",
    "pipeline_error": "The extraction failed.",
    "no_text_extracted": "No useful text could be extracted from the source.",
    "job_canceled": "The job was canceled.",
    "job_expired": "The job expired before it could finish.",
    "quota_exceeded": "The job quota has been reached.",
    "rate_limited": "Too many jobs were created recently.",
}
PUBLIC_JOB_ERROR_CODES = {
    "invalid_source_url",
    "unsupported_source_kind",
    "no_text_extracted",
    "pipeline_error",
    "job_canceled",
    "job_expired",
}


class CoordinatorError(Exception):
    error_code = "pipeline_error"
    status_code = 400


class NotFoundError(CoordinatorError):
    error_code = "not_found"
    status_code = 404


class InvalidSourceError(CoordinatorError):
    status_code = 422

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class IdempotencyConflictError(CoordinatorError):
    error_code = "idempotency_conflict"
    status_code = 409


class InvalidTransitionError(CoordinatorError):
    error_code = "invalid_transition"
    status_code = 409


class QuotaExceededError(CoordinatorError):
    error_code = "quota_exceeded"
    status_code = 429


class RateLimitedError(CoordinatorError):
    error_code = "rate_limited"
    status_code = 429


@dataclass(frozen=True)
class JobFailure:
    error_code: str
    error_message: str
    internal_error: str | None = None
    retryable: bool = True


def public_error_message(error_code: str | None, fallback: str | None = None) -> str | None:
    if error_code is None:
        return None
    return PUBLIC_ERROR_MESSAGES.get(error_code, fallback or PUBLIC_ERROR_MESSAGES["pipeline_error"])


def _public_job_error_code(error_code: str | None) -> str | None:
    if error_code is None:
        return None
    if error_code == "no_text":
        return "no_text_extracted"
    if error_code in PUBLIC_JOB_ERROR_CODES:
        return error_code
    return "pipeline_error"


def _job_response_error_code(status: str, error_code: str | None) -> str | None:
    if status in ACTIVE_STATUSES or status in USABLE_RESULT_STATUSES:
        return None
    if status == "canceled":
        return "job_canceled"
    if status == "expired":
        return "job_expired"
    return _public_job_error_code(error_code) or "pipeline_error"


def _encode_cursor(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("ascii")


def _decode_cursor(cursor: str | None) -> dict[str, Any] | None:
    if not cursor:
        return None
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("ascii"))
        payload = json.loads(decoded)
    except (ValueError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _sanitize_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in {"path", "paths", "raw_response", "headers", "api_key", "authorization"}:
                continue
            sanitized[key] = _sanitize_metadata(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_metadata(item) for item in value]
    return value


def _job_links(job_id: str) -> JobLinks:
    return JobLinks(self=f"/v1/jobs/{job_id}", result=f"/v1/jobs/{job_id}/result")


def _clamp_confidence(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.0, min(1.0, float(value)))


def _snippet(value: str | None, *, max_length: int = 280) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned[:max_length].rstrip() or None


def _fingerprint(candidate: ExtractedMentionCandidate) -> str:
    basis = "|".join(
        [
            candidate.category.strip().casefold(),
            candidate.label.strip().casefold(),
            (candidate.author_or_creator or "").strip().casefold(),
        ]
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


class JobCoordinator:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.artifact_store = LocalArtifactStore(self.settings)

    def _owns_job(self, caller: Caller, job: Job) -> bool:
        return caller.role in {"worker", "admin"} or job.owner_id == caller.subject_id

    def _get_owned_job(self, caller: Caller, job_id: str) -> Job:
        job = self.session.get(Job, job_id)
        if job is None or not self._owns_job(caller, job):
            raise NotFoundError("Job not found")
        return job

    def to_job_response(self, job: Job) -> JobResponse:
        error_code = _job_response_error_code(job.status, job.error_code)
        return JobResponse(
            job_id=job.id,
            source_url=job.source_url,
            source_kind=job.source_kind,
            status=job.status,
            current_stage=job.current_stage,
            progress=job.progress,
            attempt_count=job.attempt_count,
            error_code=error_code,
            error_message=public_error_message(error_code, job.error_message),
            created_at=job.created_at,
            updated_at=job.updated_at,
            links=_job_links(job.id),
        )

    def create_job(self, caller: Caller, source_url: str, idempotency_key: str | None) -> JobResponse:
        try:
            normalized_url, source_kind = normalize_supported_source_url(
                source_url,
                require_https=self.settings.source_require_https,
            )
        except SourceUrlError as exc:
            raise InvalidSourceError(exc.error_code, str(exc)) from exc

        if idempotency_key:
            existing = self.session.exec(
                select(Job).where(Job.owner_id == caller.subject_id, Job.idempotency_key == idempotency_key)
            ).first()
            if existing is not None:
                if existing.source_url != normalized_url:
                    raise IdempotencyConflictError("Idempotency key was already used for a different URL")
                return self.to_job_response(existing)

        self._enforce_create_quotas(caller.subject_id)
        now = utc_now()
        job = Job(
            owner_id=caller.subject_id,
            source_url=normalized_url,
            source_kind=source_kind,
            status="queued",
            current_stage=None,
            progress=0.0,
            max_attempts=3,
            next_run_at=now,
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
        )
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return self.to_job_response(job)

    def _enforce_create_quotas(self, owner_id: str) -> None:
        now = utc_now()
        burst_start = now - timedelta(minutes=1)
        day_start = now - timedelta(days=1)
        burst_count = self.session.exec(
            select(func.count()).select_from(Job).where(Job.owner_id == owner_id, Job.created_at >= burst_start)
        ).one()
        if burst_count >= self.settings.max_job_create_burst_per_minute:
            raise RateLimitedError("Too many jobs were created recently")

        day_count = self.session.exec(
            select(func.count()).select_from(Job).where(Job.owner_id == owner_id, Job.created_at >= day_start)
        ).one()
        if day_count >= self.settings.max_jobs_created_per_day:
            raise QuotaExceededError("Daily job quota has been reached")

        if self._active_job_count(owner_id) >= self.settings.max_active_jobs_per_user:
            raise QuotaExceededError("Too many jobs are already queued or running")

    def _active_job_count(self, owner_id: str) -> int:
        return self.session.exec(
            select(func.count())
            .select_from(Job)
            .where(Job.owner_id == owner_id, Job.status.in_(ACTIVE_STATUSES))
        ).one()

    def get_job(self, caller: Caller, job_id: str) -> JobResponse:
        return self.to_job_response(self._get_owned_job(caller, job_id))

    def list_jobs(self, caller: Caller, *, limit: int, cursor: str | None) -> JobListResponse:
        limit = max(1, min(limit, 100))
        statement = select(Job).where(Job.owner_id == caller.subject_id)
        payload = _decode_cursor(cursor)
        if payload and isinstance(payload.get("created_at"), str) and isinstance(payload.get("id"), str):
            created_at = datetime.fromisoformat(payload["created_at"])
            statement = statement.where(
                or_(Job.created_at < created_at, and_(Job.created_at == created_at, Job.id < payload["id"]))
            )
        rows = self.session.exec(statement.order_by(Job.created_at.desc(), Job.id.desc()).limit(limit + 1)).all()
        items = rows[:limit]
        next_cursor = None
        if len(rows) > limit and items:
            last = items[-1]
            next_cursor = _encode_cursor({"created_at": last.created_at.isoformat(), "id": last.id})
        return JobListResponse(items=[self.to_job_response(job) for job in items], next_cursor=next_cursor)

    def cancel_job(self, caller: Caller, job_id: str) -> JobResponse:
        job = self._get_owned_job(caller, job_id)
        if job.status in TERMINAL_STATUSES:
            return self.to_job_response(job)
        now = utc_now()
        if job.status == "queued":
            job.status = "canceled"
            job.current_stage = "canceled"
            job.progress = 1.0
            job.finished_at = now
            job.error_code = "job_canceled"
            job.error_message = public_error_message("job_canceled")
        else:
            job.cancel_requested_at = now
        job.updated_at = now
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return self.to_job_response(job)

    def rerun_job(self, caller: Caller, job_id: str) -> JobResponse:
        job = self._get_owned_job(caller, job_id)
        if job.status not in TERMINAL_STATUSES:
            raise InvalidTransitionError("Only terminal jobs can be rerun")
        if self._active_job_count(caller.subject_id) >= self.settings.max_active_jobs_per_user:
            raise QuotaExceededError("Too many jobs are already queued or running")
        now = utc_now()
        job.status = "queued"
        job.current_stage = None
        job.progress = 0.0
        job.locked_by = None
        job.locked_at = None
        job.heartbeat_at = None
        job.started_at = None
        job.finished_at = None
        job.cancel_requested_at = None
        job.error_code = None
        job.error_message = None
        job.internal_error = None
        job.next_run_at = now
        job.updated_at = now
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return self.to_job_response(job)

    def claim_next_job(self, worker_id: str) -> Job | None:
        if self.session.bind and self.session.bind.dialect.name == "postgresql":
            row = self.session.execute(
                text(
                    """
                    update jobs
                    set
                      status = 'running',
                      locked_by = :worker_id,
                      locked_at = now(),
                      heartbeat_at = now(),
                      started_at = coalesce(started_at, now()),
                      finished_at = null,
                      attempt_count = attempt_count + 1,
                      current_stage = 'claimed',
                      progress = 0.01,
                      error_code = null,
                      error_message = null,
                      internal_error = null,
                      updated_at = now()
                    where id = (
                      select id
                      from jobs
                      where status = 'queued'
                        and next_run_at <= now()
                        and attempt_count < max_attempts
                      order by priority desc, created_at, id
                      limit 1
                      for update skip locked
                    )
                    returning id
                    """
                ),
                {"worker_id": worker_id},
            ).first()
            self.session.commit()
            if row is None:
                return None
            return self.session.get(Job, row[0])

        now = utc_now()
        job = self.session.exec(
            select(Job)
            .where(Job.status == "queued", Job.next_run_at <= now, Job.attempt_count < Job.max_attempts)
            .order_by(Job.priority.desc(), Job.created_at, Job.id)
        ).first()
        if job is None:
            return None
        job.status = "running"
        job.locked_by = worker_id
        job.locked_at = now
        job.heartbeat_at = now
        job.started_at = job.started_at or now
        job.finished_at = None
        job.attempt_count += 1
        job.current_stage = "claimed"
        job.progress = 0.01
        job.error_code = None
        job.error_message = None
        job.internal_error = None
        job.updated_at = now
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def heartbeat(self, job_id: str, worker_id: str, *, current_stage: str | None = None, progress: float | None = None) -> None:
        job = self.session.get(Job, job_id)
        if job is None or job.locked_by != worker_id or job.status != "running":
            return
        job.heartbeat_at = utc_now()
        if current_stage is not None:
            job.current_stage = current_stage
        if progress is not None:
            job.progress = max(0.0, min(1.0, progress))
        job.updated_at = utc_now()
        self.session.add(job)
        self.session.commit()

    def recover_stale_jobs(self) -> int:
        cutoff = utc_now() - timedelta(seconds=self.settings.worker_stale_timeout_seconds)
        stale_jobs = self.session.exec(
            select(Job).where(Job.status == "running", Job.heartbeat_at < cutoff).order_by(Job.updated_at)
        ).all()
        recovered = 0
        now = utc_now()
        for job in stale_jobs:
            if job.attempt_count < job.max_attempts:
                job.status = "queued"
                job.current_stage = "stale_requeued"
                job.progress = 0.0
                job.locked_by = None
                job.locked_at = None
                job.heartbeat_at = None
                job.next_run_at = now
                job.error_code = None
                job.error_message = None
                job.internal_error = None
            else:
                job.status = "expired"
                job.current_stage = "expired"
                job.progress = 1.0
                job.locked_by = None
                job.locked_at = None
                job.heartbeat_at = None
                job.finished_at = now
                job.error_code = "job_expired"
                job.error_message = public_error_message("job_expired")
            job.updated_at = now
            self.session.add(job)
            recovered += 1
        self.session.commit()
        return recovered

    def record_pipeline_result(self, job_id: str, result: PipelineResult) -> None:
        job = self.session.get(Job, job_id)
        if job is None:
            return
        attempt_number = max(1, job.attempt_count)
        for stage_run in result.stage_runs:
            self._append_stage_run(job.owner_id, job.id, attempt_number, stage_run)
            self._record_provider_call_from_stage(job.owner_id, job.id, attempt_number, stage_run)
        for artifact in result.artifacts:
            stored = self.artifact_store.describe_existing(artifact)
            self.session.add(
                Artifact(
                    owner_id=job.owner_id,
                    job_id=job.id,
                    attempt_number=attempt_number,
                    kind=stored.kind,
                    storage_backend=stored.storage_backend,
                    storage_key=stored.storage_key,
                    media_type=stored.media_type,
                    byte_size=stored.byte_size,
                    metadata_json=stored.metadata,
                )
            )
        self.session.exec(delete(TextResult).where(TextResult.job_id == job.id))
        self.session.add(self._text_result_row(job.owner_id, job.id, attempt_number, result.text_result))

        now = utc_now()
        final_status = result.final_status if result.final_status in PIPELINE_TERMINAL_STATUSES else "failed"
        if final_status in USABLE_RESULT_STATUSES:
            error_code = None
        else:
            error_code = _public_job_error_code(result.error_code) or "pipeline_error"
        job.status = final_status
        job.source_kind = result.source_kind
        job.current_stage = "completed" if final_status in USABLE_RESULT_STATUSES else "failed"
        job.progress = 1.0
        job.finished_at = now
        job.locked_by = None
        job.locked_at = None
        job.heartbeat_at = None
        job.error_code = error_code
        job.error_message = public_error_message(error_code, result.error_message)
        job.internal_error = None
        job.updated_at = now
        self.session.add(job)

        if final_status in USABLE_RESULT_STATUSES:
            self._auto_save_mentions(job, result.candidate_mentions, result.text_result)

        self.session.commit()

    def _append_stage_run(self, owner_id: str, job_id: str, attempt_number: int, stage_run: StageOutcome) -> None:
        self.session.add(
            StageRun(
                owner_id=owner_id,
                job_id=job_id,
                attempt_number=attempt_number,
                stage=stage_run.stage,
                success=stage_run.success,
                duration_ms=max(0, stage_run.duration_ms),
                payload_json=stage_run.payload,
                error_code=None,
                error_text=stage_run.error_text,
            )
        )

    def _record_provider_call_from_stage(self, owner_id: str, job_id: str, attempt_number: int, stage_run: StageOutcome) -> None:
        payload = stage_run.payload if isinstance(stage_run.payload, dict) else {}
        if payload.get("skipped") is True:
            return
        provider = payload.get("provider")
        if stage_run.stage not in {"transcribe_audio", "multimodal_llm_extract"}:
            return
        if not isinstance(provider, str) or provider == "none":
            return
        self.session.add(
            ProviderCall(
                owner_id=owner_id,
                job_id=job_id,
                attempt_number=attempt_number,
                stage=stage_run.stage,
                provider=provider,
                model=payload.get("model") if isinstance(payload.get("model"), str) else None,
                success=stage_run.success,
                duration_ms=max(0, stage_run.duration_ms),
                input_image_count=payload.get("selected_image_count")
                if isinstance(payload.get("selected_image_count"), int)
                else None,
                error_text=stage_run.error_text,
                metadata_json=payload,
            )
        )

    def _text_result_row(self, owner_id: str, job_id: str, attempt_number: int, text_result: TextExtractionResult) -> TextResult:
        now = utc_now()
        return TextResult(
            job_id=job_id,
            owner_id=owner_id,
            attempt_number=attempt_number,
            caption_text=text_result.caption_text,
            spoken_text=text_result.spoken_text,
            visual_text=text_result.visual_text,
            image_text=text_result.image_text,
            merged_text=text_result.merged_text,
            warnings_json=text_result.warnings,
            debug_json=text_result.debug,
            created_at=now,
            updated_at=now,
        )

    def fail_claimed_job(self, job_id: str, failure: JobFailure) -> None:
        job = self.session.get(Job, job_id)
        if job is None:
            return
        now = utc_now()
        can_retry = failure.retryable and failure.error_code in RETRYABLE_ERROR_CODES and job.attempt_count < job.max_attempts
        if can_retry:
            delay = self.settings.worker_retry_base_delay_seconds * (2 ** max(0, job.attempt_count - 1))
            job.status = "queued"
            job.current_stage = "retry_scheduled"
            job.progress = 0.0
            job.next_run_at = now + timedelta(seconds=delay)
            error_code = None
            error_message = None
        else:
            job.status = "failed"
            job.current_stage = "failed"
            job.progress = 1.0
            job.finished_at = now
            error_code = _public_job_error_code(failure.error_code) or "pipeline_error"
            error_message = public_error_message(error_code, failure.error_message)
        job.locked_by = None
        job.locked_at = None
        job.heartbeat_at = None
        job.error_code = error_code
        job.error_message = error_message
        job.internal_error = failure.internal_error
        job.updated_at = now
        self.session.add(job)
        self.session.commit()

    def cancel_if_requested(self, job_id: str, worker_id: str) -> bool:
        job = self.session.get(Job, job_id)
        if job is None or job.locked_by != worker_id or job.status != "running" or job.cancel_requested_at is None:
            return False
        now = utc_now()
        job.status = "canceled"
        job.current_stage = "canceled"
        job.progress = 1.0
        job.locked_by = None
        job.locked_at = None
        job.heartbeat_at = None
        job.finished_at = now
        job.error_code = "job_canceled"
        job.error_message = public_error_message("job_canceled")
        job.internal_error = None
        job.updated_at = now
        self.session.add(job)
        self.session.commit()
        return True

    def _auto_save_mentions(
        self,
        job: Job,
        candidates: list[ExtractedMentionCandidate],
        text_result: TextExtractionResult,
    ) -> list[SavedMention]:
        debug = text_result.debug if isinstance(text_result.debug, dict) else {}
        source = debug.get("source") if isinstance(debug.get("source"), dict) else {}
        source_creator = source.get("source_creator") if isinstance(source.get("source_creator"), str) else None
        source_context_snippet = source.get("source_context_snippet") if isinstance(source.get("source_context_snippet"), str) else None
        source_context_snippet = source_context_snippet or _snippet(text_result.caption_text) or _snippet(text_result.merged_text)
        saved: list[SavedMention] = []
        for candidate in candidates:
            label = candidate.label.strip()
            if not label:
                continue
            confidence = _clamp_confidence(candidate.confidence)
            if confidence is None or confidence < MIN_AUTO_SAVE_CONFIDENCE:
                continue
            category = candidate.category if candidate.category in MENTION_CATEGORIES else "unknown"
            fingerprint = _fingerprint(candidate)
            existing = self.session.exec(
                select(SavedMention).where(
                    SavedMention.owner_id == job.owner_id,
                    SavedMention.source_job_id == job.id,
                    SavedMention.candidate_fingerprint == fingerprint,
                )
            ).first()
            evidence = candidate.evidence if isinstance(candidate.evidence, dict) else {}
            if existing is None:
                mention = SavedMention(
                    owner_id=job.owner_id,
                    source_job_id=job.id,
                    source_artifact_id=None,
                    category=category,
                    display_label=label,
                    display_author_or_creator=candidate.author_or_creator,
                    display_description=candidate.description,
                    extracted_label=label,
                    extracted_author_or_creator=candidate.author_or_creator,
                    extracted_description=candidate.description,
                    source_url=job.source_url,
                    source_platform="instagram",
                    source_creator=source_creator,
                    source_context_snippet=source_context_snippet,
                    evidence_text=candidate.evidence_text,
                    evidence_json=evidence,
                    confidence=confidence,
                    candidate_fingerprint=fingerprint,
                    save_state="active",
                    review_status="unreviewed",
                    created_by="extraction",
                )
                self.session.add(mention)
                saved.append(mention)
                continue
            existing.extracted_label = label
            existing.extracted_author_or_creator = candidate.author_or_creator
            existing.extracted_description = candidate.description
            existing.source_url = job.source_url
            existing.source_creator = source_creator
            existing.source_context_snippet = source_context_snippet
            existing.evidence_text = candidate.evidence_text
            existing.evidence_json = evidence
            existing.confidence = confidence
            if existing.review_status == "unreviewed":
                existing.category = category
                existing.display_label = label
                existing.display_author_or_creator = candidate.author_or_creator
                existing.display_description = candidate.description
            existing.updated_at = utc_now()
            self.session.add(existing)
            saved.append(existing)
        return saved

    def get_result(self, caller: Caller, job_id: str, *, include_debug: bool = False) -> JobResultResponse:
        job = self._get_owned_job(caller, job_id)
        owner_id = job.owner_id
        text_row = self.session.exec(
            select(TextResult).where(TextResult.job_id == job.id, TextResult.owner_id == owner_id)
        ).first()
        artifact_rows = self.session.exec(
            select(Artifact)
            .where(Artifact.job_id == job.id, Artifact.owner_id == owner_id)
            .order_by(Artifact.attempt_number, Artifact.created_at)
        ).all()
        stage_rows = self.session.exec(
            select(StageRun)
            .where(StageRun.job_id == job.id, StageRun.owner_id == owner_id)
            .order_by(StageRun.attempt_number, StageRun.created_at)
        ).all()
        return JobResultResponse(
            job_id=job.id,
            source_url=job.source_url,
            source_kind=job.source_kind,
            status=job.status,
            current_stage=job.current_stage,
            progress=job.progress,
            text=self._text_response(text_row, include_debug=include_debug),
            stage_runs=[self._stage_response(row, include_debug=include_debug) for row in stage_rows],
            artifacts=[self._artifact_response(row, include_debug=include_debug) for row in artifact_rows],
        )

    def _text_response(self, text_row: TextResult | None, *, include_debug: bool) -> TextResultResponse:
        if text_row is None:
            return TextResultResponse(
                caption_text=None,
                spoken_text=None,
                visual_text=None,
                image_text=None,
                merged_text="",
                warnings=["Text result has not been written yet."],
                debug=None,
            )
        return TextResultResponse(
            caption_text=text_row.caption_text,
            spoken_text=text_row.spoken_text,
            visual_text=text_row.visual_text,
            image_text=text_row.image_text,
            merged_text=text_row.merged_text,
            warnings=_json_value(text_row.warnings_json) or [],
            debug=_sanitize_metadata(_json_value(text_row.debug_json)) if include_debug else None,
        )

    def _stage_response(self, row: StageRun, *, include_debug: bool) -> StageRunResponse:
        return StageRunResponse(
            stage=row.stage,
            success=row.success,
            duration_ms=row.duration_ms,
            payload=_sanitize_metadata(_json_value(row.payload_json)) if include_debug else None,
            error_code=row.error_code,
            error_text=row.error_text if include_debug else None,
            created_at=row.created_at,
        )

    def _artifact_response(self, row: Artifact, *, include_debug: bool) -> ArtifactResponse:
        metadata = _sanitize_metadata(_json_value(row.metadata_json)) if include_debug else None
        return ArtifactResponse(
            artifact_id=row.id,
            kind=row.kind,
            storage_backend=row.storage_backend,
            media_type=row.media_type,
            byte_size=row.byte_size,
            metadata=metadata,
            created_at=row.created_at,
        )

    def to_saved_mention_response(self, mention: SavedMention) -> SavedMentionResponse:
        return SavedMentionResponse(
            mention_id=mention.id,
            category=mention.category,
            label=mention.display_label,
            author_or_creator=mention.display_author_or_creator,
            description=mention.display_description,
            source_job_id=mention.source_job_id,
            source_url=mention.source_url,
            source_platform=mention.source_platform,
            source_creator=mention.source_creator,
            source_context_snippet=mention.source_context_snippet,
            confidence=mention.confidence,
            created_at=mention.created_at,
            updated_at=mention.updated_at,
        )

    def _get_owned_mention(self, caller: Caller, mention_id: str) -> SavedMention:
        mention = self.session.get(SavedMention, mention_id)
        if mention is None or mention.owner_id != caller.subject_id:
            raise NotFoundError("Saved mention not found")
        return mention

    def list_mentions(
        self,
        caller: Caller,
        *,
        limit: int,
        cursor: str | None,
        category: str | None = None,
        review_status: str | None = None,
        save_state: str = "active",
        source_creator: str | None = None,
        q: str | None = None,
        sort: str = "created_desc",
    ) -> SavedMentionListResponse:
        limit = max(1, min(limit, 100))
        statement = select(SavedMention).where(SavedMention.owner_id == caller.subject_id)
        if category:
            statement = statement.where(SavedMention.category == category)
        if review_status:
            statement = statement.where(SavedMention.review_status == review_status)
        if save_state:
            statement = statement.where(SavedMention.save_state == save_state)
        if review_status is None:
            statement = statement.where(
                or_(
                    SavedMention.review_status == "reviewed",
                    SavedMention.confidence.is_(None),
                    SavedMention.confidence >= MIN_AUTO_SAVE_CONFIDENCE,
                )
            )
        if source_creator:
            statement = statement.where(SavedMention.source_creator == source_creator)
        if q:
            query = q.strip()
            if self.session.bind and self.session.bind.dialect.name == "postgresql":
                search_document = func.to_tsvector(
                    "simple",
                    func.concat(
                        func.coalesce(SavedMention.display_label, ""),
                        " ",
                        func.coalesce(SavedMention.display_author_or_creator, ""),
                        " ",
                        func.coalesce(SavedMention.display_description, ""),
                    ),
                )
                statement = statement.where(search_document.op("@@")(func.plainto_tsquery("simple", query)))
            else:
                pattern = f"%{query}%"
                statement = statement.where(
                    or_(
                        SavedMention.display_label.ilike(pattern),
                        SavedMention.display_author_or_creator.ilike(pattern),
                        SavedMention.display_description.ilike(pattern),
                    )
                )
        payload = _decode_cursor(cursor)
        if payload and sort == "created_desc" and isinstance(payload.get("created_at"), str) and isinstance(payload.get("id"), str):
            created_at = datetime.fromisoformat(payload["created_at"])
            statement = statement.where(
                or_(
                    SavedMention.created_at < created_at,
                    and_(SavedMention.created_at == created_at, SavedMention.id < payload["id"]),
                )
            )

        if sort == "confidence_asc":
            statement = statement.order_by(SavedMention.confidence.asc().nullslast(), SavedMention.created_at.desc(), SavedMention.id.desc())
        elif sort == "confidence_desc":
            statement = statement.order_by(SavedMention.confidence.desc().nullslast(), SavedMention.created_at.desc(), SavedMention.id.desc())
        else:
            statement = statement.order_by(SavedMention.created_at.desc(), SavedMention.id.desc())

        rows = self.session.exec(statement.limit(limit + 1)).all()
        items = rows[:limit]
        next_cursor = None
        if sort == "created_desc" and len(rows) > limit and items:
            last = items[-1]
            next_cursor = _encode_cursor({"created_at": last.created_at.isoformat(), "id": last.id})
        return SavedMentionListResponse(
            items=[self.to_saved_mention_response(mention) for mention in items],
            next_cursor=next_cursor,
        )

    def get_mention(self, caller: Caller, mention_id: str) -> SavedMentionResponse:
        return self.to_saved_mention_response(self._get_owned_mention(caller, mention_id))

    def update_mention(
        self,
        caller: Caller,
        mention_id: str,
        *,
        label: str | None = None,
        author_or_creator: str | None = None,
        description: str | None = None,
        category: str | None = None,
    ) -> SavedMentionResponse:
        mention = self._get_owned_mention(caller, mention_id)
        if category is not None and category not in MENTION_CATEGORIES:
            raise InvalidSourceError("invalid_category", "Category is not valid")
        if label is not None:
            mention.display_label = label
        if author_or_creator is not None:
            mention.display_author_or_creator = author_or_creator or None
        if description is not None:
            mention.display_description = description or None
        if category is not None:
            mention.category = category
        mention.review_status = "reviewed"
        mention.updated_at = utc_now()
        self.session.add(mention)
        self.session.commit()
        self.session.refresh(mention)
        return self.to_saved_mention_response(mention)

    def confirm_mention(self, caller: Caller, mention_id: str) -> SavedMentionResponse:
        mention = self._get_owned_mention(caller, mention_id)
        mention.review_status = "reviewed"
        mention.updated_at = utc_now()
        self.session.add(mention)
        self.session.commit()
        self.session.refresh(mention)
        return self.to_saved_mention_response(mention)

    def delete_mention(self, caller: Caller, mention_id: str) -> SavedMentionResponse:
        mention = self._get_owned_mention(caller, mention_id)
        mention.save_state = "deleted"
        mention.updated_at = utc_now()
        self.session.add(mention)
        self.session.commit()
        self.session.refresh(mention)
        return self.to_saved_mention_response(mention)
