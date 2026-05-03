from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, JSON, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel


JOB_STATUSES = ("queued", "running", "succeeded", "partial", "failed", "canceled", "expired")
TERMINAL_JOB_STATUSES = ("succeeded", "partial", "failed", "canceled", "expired")
MENTION_CATEGORIES = ("book", "product", "place", "newsletter", "person", "unknown")
MENTION_SAVE_STATES = ("active", "deleted")
MENTION_REVIEW_STATUSES = ("unreviewed", "reviewed")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid4())


def uuid_column(
    *,
    primary_key: bool = False,
    nullable: bool = False,
    foreign_key: str | None = None,
    ondelete: str | None = None,
) -> Column:
    args = []
    if foreign_key is not None:
        args.append(ForeignKey(foreign_key, ondelete=ondelete))
    return Column(Uuid(as_uuid=False), *args, primary_key=primary_key, nullable=nullable)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class Job(SQLModel, table=True):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(f"status in ({_quoted(JOB_STATUSES)})", name="jobs_status_check"),
        CheckConstraint("progress >= 0 and progress <= 1", name="jobs_progress_check"),
        CheckConstraint("attempt_count >= 0", name="jobs_attempt_count_check"),
        CheckConstraint("max_attempts >= 1", name="jobs_max_attempts_check"),
        Index("jobs_owner_created_id_idx", "owner_id", "created_at", "id"),
        Index(
            "jobs_queued_claim_idx",
            "status",
            "next_run_at",
            "priority",
            "created_at",
            "id",
            sqlite_where=text("status = 'queued'"),
            postgresql_where=text("status = 'queued'"),
        ),
        Index(
            "jobs_running_heartbeat_idx",
            "status",
            "heartbeat_at",
            sqlite_where=text("status = 'running'"),
            postgresql_where=text("status = 'running'"),
        ),
        Index(
            "jobs_owner_idempotency_uidx",
            "owner_id",
            "idempotency_key",
            unique=True,
            sqlite_where=text("idempotency_key is not null"),
            postgresql_where=text("idempotency_key is not null"),
        ),
    )

    id: str = Field(default_factory=new_uuid, sa_column=uuid_column(primary_key=True))
    owner_id: str = Field(sa_column=uuid_column())
    source_url: str
    source_kind: str = Field(default="unknown", index=True)
    status: str = Field(default="queued", index=True)
    current_stage: str | None = None
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    priority: int = 0
    attempt_count: int = 0
    max_attempts: int = 3
    locked_by: str | None = None
    locked_at: datetime | None = None
    heartbeat_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    next_run_at: datetime = Field(default_factory=utc_now)
    cancel_requested_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    internal_error: str | None = None
    idempotency_key: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class StageRun(SQLModel, table=True):
    __tablename__ = "job_stage_runs"
    __table_args__ = (
        CheckConstraint("attempt_number >= 1", name="job_stage_runs_attempt_number_check"),
        CheckConstraint("duration_ms >= 0", name="job_stage_runs_duration_ms_check"),
        Index("job_stage_runs_job_created_idx", "job_id", "created_at", "id"),
        Index("job_stage_runs_owner_job_created_idx", "owner_id", "job_id", "created_at", "id"),
    )

    id: str = Field(default_factory=new_uuid, sa_column=uuid_column(primary_key=True))
    owner_id: str = Field(sa_column=uuid_column())
    job_id: str = Field(sa_column=uuid_column(foreign_key="jobs.id", ondelete="CASCADE"))
    attempt_number: int
    stage: str = Field(index=True)
    success: bool
    duration_ms: int
    payload_json: object | None = Field(default=None, sa_column=Column("payload", JSON, nullable=True))
    error_code: str | None = None
    error_text: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class Artifact(SQLModel, table=True):
    __tablename__ = "artifacts"
    __table_args__ = (
        CheckConstraint("attempt_number >= 1", name="artifacts_attempt_number_check"),
        CheckConstraint("byte_size is null or byte_size >= 0", name="artifacts_byte_size_check"),
        Index("artifacts_job_kind_created_idx", "job_id", "kind", "created_at", "id"),
        Index("artifacts_owner_job_kind_created_idx", "owner_id", "job_id", "kind", "created_at", "id"),
    )

    id: str = Field(default_factory=new_uuid, sa_column=uuid_column(primary_key=True))
    owner_id: str = Field(sa_column=uuid_column())
    job_id: str = Field(sa_column=uuid_column(foreign_key="jobs.id", ondelete="CASCADE"))
    attempt_number: int
    kind: str = Field(index=True)
    storage_backend: str
    storage_key: str
    media_type: str | None = None
    byte_size: int | None = None
    sha256: str | None = None
    metadata_json: object | None = Field(default=None, sa_column=Column("metadata", JSON, nullable=True))
    created_at: datetime = Field(default_factory=utc_now)


class TextResult(SQLModel, table=True):
    __tablename__ = "text_results"
    __table_args__ = (
        CheckConstraint("attempt_number >= 1", name="text_results_attempt_number_check"),
        Index("text_results_owner_job_idx", "owner_id", "job_id"),
    )

    job_id: str = Field(sa_column=uuid_column(primary_key=True, foreign_key="jobs.id", ondelete="CASCADE"))
    owner_id: str = Field(sa_column=uuid_column())
    attempt_number: int
    caption_text: str | None = None
    spoken_text: str | None = None
    visual_text: str | None = None
    image_text: str | None = None
    merged_text: str
    warnings_json: object = Field(default_factory=list, sa_column=Column("warnings", JSON, nullable=False))
    debug_json: object | None = Field(default=None, sa_column=Column("debug", JSON, nullable=True))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ProviderCall(SQLModel, table=True):
    __tablename__ = "provider_calls"
    __table_args__ = (
        CheckConstraint("attempt_number >= 1", name="provider_calls_attempt_number_check"),
        CheckConstraint("duration_ms >= 0", name="provider_calls_duration_ms_check"),
        Index("provider_calls_job_created_idx", "job_id", "created_at", "id"),
        Index("provider_calls_owner_job_created_idx", "owner_id", "job_id", "created_at", "id"),
    )

    id: str = Field(default_factory=new_uuid, sa_column=uuid_column(primary_key=True))
    owner_id: str = Field(sa_column=uuid_column())
    job_id: str = Field(sa_column=uuid_column(foreign_key="jobs.id", ondelete="CASCADE"))
    attempt_number: int
    stage: str
    provider: str
    model: str | None = None
    success: bool
    duration_ms: int
    input_token_count: int | None = None
    output_token_count: int | None = None
    input_image_count: int | None = None
    estimated_cost_usd: float | None = None
    error_code: str | None = None
    error_text: str | None = None
    metadata_json: object | None = Field(default=None, sa_column=Column("metadata", JSON, nullable=True))
    created_at: datetime = Field(default_factory=utc_now)


class SavedMention(SQLModel, table=True):
    __tablename__ = "saved_mentions"
    __table_args__ = (
        CheckConstraint(f"category in ({_quoted(MENTION_CATEGORIES)})", name="saved_mentions_category_check"),
        CheckConstraint(
            f"save_state in ({_quoted(MENTION_SAVE_STATES)})",
            name="saved_mentions_save_state_check",
        ),
        CheckConstraint(
            f"review_status in ({_quoted(MENTION_REVIEW_STATUSES)})",
            name="saved_mentions_review_status_check",
        ),
        CheckConstraint("confidence is null or (confidence >= 0 and confidence <= 1)", name="saved_mentions_confidence_check"),
        UniqueConstraint("source_job_id", "candidate_fingerprint", name="saved_mentions_source_candidate_uidx"),
        Index("saved_mentions_owner_created_id_idx", "owner_id", "created_at", "id"),
        Index("saved_mentions_owner_category_created_idx", "owner_id", "category", "created_at", "id"),
        Index(
            "saved_mentions_owner_creator_created_idx",
            "owner_id",
            "source_creator",
            "created_at",
            "id",
            sqlite_where=text("source_creator is not null"),
            postgresql_where=text("source_creator is not null"),
        ),
        Index("saved_mentions_source_job_idx", "source_job_id"),
    )

    id: str = Field(default_factory=new_uuid, sa_column=uuid_column(primary_key=True))
    owner_id: str = Field(sa_column=uuid_column())
    source_job_id: str = Field(sa_column=uuid_column(foreign_key="jobs.id", ondelete="CASCADE"))
    source_artifact_id: str | None = Field(
        default=None,
        sa_column=uuid_column(nullable=True, foreign_key="artifacts.id", ondelete="SET NULL"),
    )
    category: str = Field(default="unknown", index=True)
    display_label: str
    display_author_or_creator: str | None = None
    display_description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    extracted_label: str
    extracted_author_or_creator: str | None = None
    extracted_description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    source_url: str
    source_platform: str = "instagram"
    source_creator: str | None = Field(default=None, index=True)
    source_context_snippet: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    evidence_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    evidence_json: object = Field(default_factory=dict, sa_column=Column("evidence", JSON, nullable=False))
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    candidate_fingerprint: str
    save_state: str = Field(default="active", index=True)
    review_status: str = Field(default="unreviewed", index=True)
    created_by: str = "extraction"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
