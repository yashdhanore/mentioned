from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.auth import Caller
from app.config import Settings
from app.models import Artifact, ProviderCall, SavedMention, StageRun, TextResult
from app.services.job_coordinator import (
    IdempotencyConflictError,
    JobCoordinator,
    JobFailure,
    NotFoundError,
)
from extractor.types import ArtifactRecord, ExtractedMentionCandidate, PipelineResult, StageOutcome, TextExtractionResult


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
    )


def _caller(user_id: str = "00000000-0000-4000-8000-000000000111") -> Caller:
    return Caller(subject_id=user_id, role="user")


def _pipeline_result(tmp_path: Path) -> PipelineResult:
    artifact = tmp_path / "result.json"
    artifact.write_text("{}", encoding="utf-8")
    return PipelineResult(
        source_kind="instagram_reel",
        final_status="succeeded",
        error_code=None,
        error_message=None,
        stage_runs=[
            StageOutcome(
                stage="assemble_text_result",
                success=True,
                duration_ms=5,
                payload={"path": "/private/tmp/result.json", "merged_text_length": 25},
            ),
            StageOutcome(
                stage="multimodal_llm_extract",
                success=True,
                duration_ms=10,
                payload={"provider": "openai", "model": "gpt-5.4-nano", "selected_image_count": 1},
            ),
        ],
        artifacts=[ArtifactRecord(kind="text_result", path=str(artifact), metadata={"path": str(artifact), "warning_count": 0})],
        text_result=TextExtractionResult(
            caption_text="Read this",
            spoken_text=None,
            visual_text="The Visible Book by A. Writer",
            image_text=None,
            merged_text="The Visible Book by A. Writer",
            warnings=[],
            debug={"source": {"source_creator": "creator", "source_context_snippet": "Read this"}},
        ),
        candidate_mentions=[
            ExtractedMentionCandidate(
                label="The Visible Book",
                author_or_creator="A. Writer",
                category="book",
                confidence=0.91,
                evidence={"source": "test"},
                evidence_text="The Visible Book by A. Writer",
            )
        ],
    )


def test_create_job_is_owner_scoped_and_idempotent(tmp_path: Path) -> None:
    engine = _engine()
    with Session(engine) as session:
        coordinator = JobCoordinator(session, _settings(tmp_path))
        first = coordinator.create_job(
            _caller(),
            "https://www.instagram.com/reel/abc/?utm_source=x",
            "idem-123456",
        )
        replay = coordinator.create_job(
            _caller(),
            "https://www.instagram.com/reel/abc/",
            "idem-123456",
        )

        assert replay.job_id == first.job_id
        assert replay.source_url == "https://www.instagram.com/reel/abc/"
        with pytest.raises(IdempotencyConflictError):
            coordinator.create_job(_caller(), "https://www.instagram.com/reel/other/", "idem-123456")
        with pytest.raises(NotFoundError):
            coordinator.get_job(_caller("00000000-0000-4000-8000-000000000222"), first.job_id)


def test_claim_failure_retry_and_rerun_preserve_attempt_history(tmp_path: Path) -> None:
    engine = _engine()
    with Session(engine) as session:
        coordinator = JobCoordinator(session, _settings(tmp_path))
        created = coordinator.create_job(_caller(), "https://www.instagram.com/reel/abc/", None)
        claimed = coordinator.claim_next_job("worker-a")
        assert claimed is not None
        assert claimed.id == created.job_id
        assert claimed.attempt_count == 1
        assert coordinator.claim_next_job("worker-b") is None

        coordinator.fail_claimed_job(
            claimed.id,
            JobFailure(error_code="pipeline_error", error_message="failed", internal_error="stack", retryable=True),
        )
        retried = coordinator.claim_next_job("worker-b")
        assert retried is not None
        assert retried.attempt_count == 2

        coordinator.record_pipeline_result(retried.id, _pipeline_result(tmp_path))
        result = coordinator.get_result(_caller(), retried.id)
        assert result.status == "succeeded"
        assert result.text.debug is None
        assert result.stage_runs[0].payload is None
        assert result.artifacts[0].metadata is None

        mention_count = len(session.exec(select(SavedMention).where(SavedMention.source_job_id == retried.id)).all())
        assert mention_count == 1
        owner_id = _caller().subject_id
        text_row = session.get(TextResult, retried.id)
        assert text_row is not None
        assert text_row.owner_id == owner_id
        assert all(
            artifact.owner_id == owner_id
            for artifact in session.exec(select(Artifact).where(Artifact.job_id == retried.id)).all()
        )
        assert all(
            stage.owner_id == owner_id
            for stage in session.exec(select(StageRun).where(StageRun.job_id == retried.id)).all()
        )
        provider_call = session.exec(select(ProviderCall).where(ProviderCall.job_id == retried.id)).one()
        assert provider_call.owner_id == owner_id
        coordinator.rerun_job(_caller(), retried.id)
        assert len(session.exec(select(Artifact).where(Artifact.job_id == retried.id)).all()) == 1
        assert len(session.exec(select(StageRun).where(StageRun.job_id == retried.id)).all()) == 2


def test_get_result_filters_child_rows_by_owner_id(tmp_path: Path) -> None:
    engine = _engine()
    with Session(engine) as session:
        coordinator = JobCoordinator(session, _settings(tmp_path))
        created = coordinator.create_job(_caller(), "https://www.instagram.com/reel/abc/", None)
        claimed = coordinator.claim_next_job("worker-a")
        assert claimed is not None
        coordinator.record_pipeline_result(claimed.id, _pipeline_result(tmp_path))

        other_owner = "00000000-0000-4000-8000-000000000222"
        text_row = session.get(TextResult, created.job_id)
        assert text_row is not None
        text_row.owner_id = other_owner
        for artifact in session.exec(select(Artifact).where(Artifact.job_id == created.job_id)).all():
            artifact.owner_id = other_owner
            session.add(artifact)
        for stage in session.exec(select(StageRun).where(StageRun.job_id == created.job_id)).all():
            stage.owner_id = other_owner
            session.add(stage)
        session.add(text_row)
        session.commit()

        result = coordinator.get_result(_caller(), created.job_id)
        assert result.text.merged_text == ""
        assert result.stage_runs == []
        assert result.artifacts == []


def test_skipped_multimodal_stage_does_not_record_provider_call(tmp_path: Path) -> None:
    engine = _engine()
    with Session(engine) as session:
        coordinator = JobCoordinator(session, _settings(tmp_path))
        created = coordinator.create_job(_caller(), "https://www.instagram.com/reel/abc/", None)
        claimed = coordinator.claim_next_job("worker-a")
        assert claimed is not None

        artifact = tmp_path / "result.json"
        artifact.write_text("{}", encoding="utf-8")
        coordinator.record_pipeline_result(
            claimed.id,
            PipelineResult(
                source_kind="instagram_reel",
                final_status="partial",
                error_code=None,
                error_message=None,
                stage_runs=[
                    StageOutcome(
                        stage="multimodal_llm_extract",
                        success=True,
                        duration_ms=1,
                        payload={
                            "skipped": True,
                            "skip_reason": "llm_call_limit_exhausted",
                            "provider": "openai",
                            "model": "gpt-5.4-nano",
                            "selected_image_count": 3,
                        },
                    )
                ],
                artifacts=[
                    ArtifactRecord(kind="text_result", path=str(artifact), metadata={"warning_count": 0}),
                ],
                text_result=TextExtractionResult(
                    caption_text="caption",
                    spoken_text=None,
                    visual_text="OCR fallback",
                    image_text=None,
                    merged_text="Visible text:\nOCR fallback",
                    warnings=[],
                    debug={"nonfatal_errors": ["multimodal_llm_extract"]},
                ),
                candidate_mentions=[],
            ),
        )

        assert session.exec(select(ProviderCall).where(ProviderCall.job_id == claimed.id)).all() == []
        stage_run = session.exec(select(StageRun).where(StageRun.job_id == claimed.id)).one()
        assert stage_run.success is True
        assert stage_run.payload_json["skip_reason"] == "llm_call_limit_exhausted"


def test_saved_mention_update_confirm_and_soft_delete(tmp_path: Path) -> None:
    engine = _engine()
    with Session(engine) as session:
        coordinator = JobCoordinator(session, _settings(tmp_path))
        created = coordinator.create_job(_caller(), "https://www.instagram.com/reel/abc/", None)
        claimed = coordinator.claim_next_job("worker-a")
        assert claimed is not None
        coordinator.record_pipeline_result(claimed.id, _pipeline_result(tmp_path))
        mention = coordinator.list_mentions(_caller(), limit=20, cursor=None).items[0]

        updated = coordinator.update_mention(
            _caller(),
            mention.mention_id,
            label="Corrected Book",
            category="book",
        )
        assert updated.label == "Corrected Book"
        updated_row = session.get(SavedMention, mention.mention_id)
        assert updated_row is not None
        assert updated_row.review_status == "reviewed"
        assert coordinator.list_mentions(_caller(), limit=20, cursor=None, q="Corrected").items[0].mention_id == mention.mention_id
        with pytest.raises(NotFoundError):
            coordinator.get_mention(_caller("00000000-0000-4000-8000-000000000222"), mention.mention_id)
        with pytest.raises(NotFoundError):
            coordinator.update_mention(
                _caller("00000000-0000-4000-8000-000000000222"),
                mention.mention_id,
                label="Other User Edit",
            )
        with pytest.raises(NotFoundError):
            coordinator.confirm_mention(_caller("00000000-0000-4000-8000-000000000222"), mention.mention_id)
        with pytest.raises(NotFoundError):
            coordinator.delete_mention(_caller("00000000-0000-4000-8000-000000000222"), mention.mention_id)

        confirmed = coordinator.confirm_mention(_caller(), mention.mention_id)
        assert confirmed.label == "Corrected Book"
        confirmed_row = session.get(SavedMention, mention.mention_id)
        assert confirmed_row is not None
        assert confirmed_row.review_status == "reviewed"

        deleted = coordinator.delete_mention(_caller(), mention.mention_id)
        assert deleted.label == "Corrected Book"
        deleted_row = session.get(SavedMention, mention.mention_id)
        assert deleted_row is not None
        assert deleted_row.save_state == "deleted"
        assert coordinator.list_mentions(_caller(), limit=20, cursor=None).items == []
        assert created.job_id == claimed.id


def test_low_confidence_unreviewed_extraction_mentions_are_hidden_by_default(tmp_path: Path) -> None:
    engine = _engine()
    with Session(engine) as session:
        coordinator = JobCoordinator(session, _settings(tmp_path))
        created = coordinator.create_job(_caller(), "https://www.instagram.com/reel/abc/", None)
        low_confidence = SavedMention(
            owner_id=_caller().subject_id,
            source_job_id=created.job_id,
            category="book",
            display_label="SSS",
            extracted_label="SSS",
            source_url="https://www.instagram.com/reel/abc/",
            source_platform="instagram",
            evidence_json={"pattern": "title_case_line"},
            confidence=0.35,
            candidate_fingerprint="low-confidence",
            save_state="active",
            review_status="unreviewed",
            created_by="extraction",
        )
        session.add(low_confidence)
        session.commit()

        assert coordinator.list_mentions(_caller(), limit=20, cursor=None).items == []

        low_confidence.review_status = "reviewed"
        session.add(low_confidence)
        session.commit()

        items = coordinator.list_mentions(_caller(), limit=20, cursor=None).items
        assert len(items) == 1
        assert items[0].label == "SSS"


def test_low_confidence_pipeline_candidates_are_not_auto_saved(tmp_path: Path) -> None:
    engine = _engine()
    with Session(engine) as session:
        coordinator = JobCoordinator(session, _settings(tmp_path))
        created = coordinator.create_job(_caller(), "https://www.instagram.com/reel/abc/", None)
        claimed = coordinator.claim_next_job("worker-a")
        assert claimed is not None
        result = _pipeline_result(tmp_path)
        result.candidate_mentions = [
            ExtractedMentionCandidate(
                label="SSS",
                author_or_creator=None,
                category="book",
                confidence=0.35,
                evidence={"source": "test"},
                evidence_text="SSS",
            )
        ]

        coordinator.record_pipeline_result(claimed.id, result)

        assert session.exec(select(SavedMention).where(SavedMention.source_job_id == claimed.id)).all() == []
        assert created.job_id == claimed.id
