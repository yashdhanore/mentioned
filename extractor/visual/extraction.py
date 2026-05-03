from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from app.config import Settings
from extractor.clients.tesseract import ocr_image
from extractor.types import ArtifactRecord, StageOutcome
from extractor.visual.crops import generate_visual_inputs
from extractor.visual.models import (
    OpenAIVisualResponse,
    SCHEMA_VERSION,
    VisualExtractionResult,
    VisualImage,
    VisualReconstruction,
)
from extractor.visual.openai_provider import run_openai_visual_reconstruction


GENERIC_TEXT_VALUES = {"instagram", "instagram reel", "instagram post", "instagram photo"}


def _write_json(path: Path, content: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=True, indent=2), encoding="utf-8")


def _duration_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _stage_outcome(
    *,
    stage: str,
    start: float,
    success: bool,
    payload: dict[str, Any] | None = None,
    error_text: str | None = None,
) -> StageOutcome:
    return StageOutcome(
        stage=stage,
        success=success,
        duration_ms=_duration_ms(start),
        payload=payload,
        error_text=error_text,
    )


def _clean_section_text(value: str | None) -> str | None:
    if value is None:
        return None
    lines = [" ".join(line.split()) for line in value.splitlines()]
    cleaned_lines = [line for line in lines if line]
    if not cleaned_lines:
        return None
    return "\n".join(cleaned_lines)


def _dedupe_text(values: list[str | None]) -> str | None:
    lines: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean_section_text(value)
        if cleaned is None:
            continue
        for line in cleaned.splitlines():
            normalized = line.casefold()
            if normalized in GENERIC_TEXT_VALUES or normalized in seen:
                continue
            seen.add(normalized)
            lines.append(line)
    if not lines:
        return None
    return "\n".join(lines)


def _ocr_visual_inputs(
    images: list[VisualImage],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None, str | None]:
    frame_entries: list[dict[str, Any]] = []
    post_image_entries: list[dict[str, Any]] = []
    for image in images:
        raw_text = ocr_image(image.path)
        text = _clean_section_text(raw_text)
        entry = {
            "id": image.id,
            "role": image.role,
            "source_surface": image.source_surface,
            "source_image_id": image.source_image_id,
            "path": str(image.path),
            "bbox_normalized": list(image.bbox_normalized),
            "text": text or "",
            "has_text": bool(text),
        }
        if image.source_surface == "frame":
            frame_entries.append(entry)
        else:
            post_image_entries.append(entry)

    def fallback_text(entries: list[dict[str, Any]]) -> str | None:
        focused = [entry["text"] for entry in entries if entry["role"] != "full"]
        full = [entry["text"] for entry in entries if entry["role"] == "full"]
        return _dedupe_text([*focused, *full])

    return (
        frame_entries,
        post_image_entries,
        fallback_text(frame_entries),
        fallback_text(post_image_entries),
    )


def _validate_reconstruction_sources(
    reconstruction: VisualReconstruction,
    *,
    selected_images: list[VisualImage],
    crops: list[VisualImage],
) -> None:
    selected_ids = {entry.id for entry in selected_images}
    crop_ids = {entry.id for entry in crops}
    for block in reconstruction.visible_text_blocks:
        if not block.source_image_ids and not block.source_crop_ids:
            raise ValueError("visible_text_blocks entries must cite at least one source image or crop")
        unknown_images = [source_id for source_id in block.source_image_ids if source_id not in selected_ids]
        unknown_crops = [source_id for source_id in block.source_crop_ids if source_id not in crop_ids]
        if unknown_images or unknown_crops:
            raise ValueError(f"OpenAI output cited unknown source IDs: {unknown_images + unknown_crops}")

    for candidate in reconstruction.candidate_mentions:
        unknown_images = [source_id for source_id in candidate.source_image_ids if source_id not in selected_ids]
        unknown_crops = [source_id for source_id in candidate.source_crop_ids if source_id not in crop_ids]
        if unknown_images or unknown_crops:
            raise ValueError(f"candidate_mentions entries cited unknown source IDs: {unknown_images + unknown_crops}")
        if (
            candidate.evidence_basis == "partial_cover_inference"
            and not candidate.source_image_ids
            and not candidate.source_crop_ids
        ):
            raise ValueError("partial-cover inferred candidates must cite source image or crop IDs")


def _llm_input_manifest(
    *,
    job_id: str,
    source_url: str,
    source_kind: str,
    caption_text: str | None,
    selected_images: list[VisualImage],
    crops: list[VisualImage],
    llm_images: list[VisualImage],
    ocr_visual_text: str | None,
    ocr_image_text: str | None,
    frame_ocr_entries: list[dict[str, Any]],
    image_ocr_entries: list[dict[str, Any]],
    settings: Settings,
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "source_url": source_url,
        "source_kind": source_kind,
        "caption_text": caption_text,
        "ocr_text": {
            "frame_text": ocr_visual_text,
            "post_image_text": ocr_image_text,
            "frame_entry_count": len(frame_ocr_entries),
            "post_image_entry_count": len(image_ocr_entries),
        },
        "selected_images": [entry.manifest_record() for entry in selected_images],
        "crops": [entry.manifest_record() for entry in crops],
        "llm_images": [entry.manifest_record() for entry in llm_images],
        "expected_output_schema_version": SCHEMA_VERSION,
        "provider": settings.multimodal_llm_provider,
        "model": settings.openai_multimodal_model,
    }


def _write_success_llm_artifacts(
    *,
    artifact_dir: Path,
    llm_response: OpenAIVisualResponse,
    artifacts: list[ArtifactRecord],
) -> tuple[Path, Path, Path]:
    output_path = artifact_dir / "llm_output.json"
    usage_path = artifact_dir / "llm_usage.json"
    reconstruction_path = artifact_dir / "visual_reconstruction.json"
    _write_json(
        output_path,
        {
            "schema_version": SCHEMA_VERSION,
            "provider": "openai",
            "success": True,
            "raw_response": llm_response.raw_response,
        },
    )
    _write_json(
        usage_path,
        {
            "schema_version": SCHEMA_VERSION,
            "provider": "openai",
            "usage": llm_response.usage,
        },
    )
    _write_json(
        reconstruction_path,
        llm_response.reconstruction.model_dump(mode="json"),
    )
    artifacts.extend(
        [
            ArtifactRecord(
                kind="llm_output",
                path=str(output_path),
                metadata={"provider": "openai", "validation_status": "valid"},
            ),
            ArtifactRecord(
                kind="llm_usage",
                path=str(usage_path),
                metadata={"provider": "openai"},
            ),
            ArtifactRecord(
                kind="visual_reconstruction",
                path=str(reconstruction_path),
                metadata={
                    "schema_version": SCHEMA_VERSION,
                    "candidate_mentions_count": len(llm_response.reconstruction.candidate_mentions),
                },
            ),
        ]
    )
    return output_path, usage_path, reconstruction_path


def _write_failed_llm_artifact(
    *,
    artifact_dir: Path,
    provider: str,
    model: str,
    error_text: str,
    artifacts: list[ArtifactRecord],
) -> Path:
    output_path = artifact_dir / "llm_output.json"
    _write_json(
        output_path,
        {
            "schema_version": SCHEMA_VERSION,
            "provider": provider,
            "model": model,
            "success": False,
            "error_text": error_text,
        },
    )
    artifacts.append(
        ArtifactRecord(
            kind="llm_output",
            path=str(output_path),
            metadata={"provider": provider, "validation_status": "rejected"},
        )
    )
    return output_path


def extract_visual_text(
    *,
    job_id: str,
    artifact_dir: Path,
    source_url: str,
    source_kind: str,
    selected_frames: list[Path],
    selected_post_images: list[Path],
    caption_text: str | None,
    settings: Settings,
) -> VisualExtractionResult:
    artifacts: list[ArtifactRecord] = []
    warnings: list[str] = []
    nonfatal_errors: list[str] = []
    stage_runs: list[StageOutcome] = []

    generate_start = time.perf_counter()
    try:
        bundle = generate_visual_inputs(
            selected_frames=selected_frames,
            selected_post_images=selected_post_images,
            artifact_dir=artifact_dir,
            settings=settings,
        )
        image_manifest_path = artifact_dir / "image_selection_manifest.json"
        _write_json(image_manifest_path, bundle.image_selection_manifest)
        artifacts.extend(
            [
                ArtifactRecord(
                    kind="image_selection_manifest",
                    path=str(image_manifest_path),
                    metadata={
                        "selected_image_count": len(bundle.selected_images),
                        "crop_count": len(bundle.crops),
                        "llm_image_count": len(bundle.llm_images),
                    },
                ),
                ArtifactRecord(
                    kind="crops",
                    path=str(artifact_dir / "crops"),
                    metadata={"crop_count": len(bundle.crops)},
                ),
            ]
        )
        stage_runs.append(
            _stage_outcome(
                stage="generate_crops",
                start=generate_start,
                success=True,
                payload={
                    "selected_image_count": len(bundle.selected_images),
                    "crop_count": len(bundle.crops),
                    "llm_image_count": len(bundle.llm_images),
                },
            )
        )
    except Exception as exc:
        error_text = str(exc)
        warnings.append(f"Crop generation failed: {error_text}")
        nonfatal_errors.append("generate_crops")
        stage_runs.append(
            _stage_outcome(
                stage="generate_crops",
                start=generate_start,
                success=False,
                error_text=error_text,
            )
        )
        return VisualExtractionResult(
            visual_text=None,
            image_text=None,
            warnings=warnings,
            nonfatal_errors=nonfatal_errors,
            artifacts=artifacts,
            stage_runs=stage_runs,
            debug={
                "visual_reconstruction_provider": settings.multimodal_llm_provider,
                "visual_reconstruction_model": settings.openai_multimodal_model,
                "ocr_openai_comparison": {
                    "frame_text_source": "none",
                    "post_image_text_source": "none",
                    "ocr_visual_text_length": 0,
                    "ocr_image_text_length": 0,
                    "openai_frame_text_length": 0,
                    "openai_post_image_text_length": 0,
                    "candidate_mentions_count": 0,
                    "partial_cover_inference_count": 0,
                    "ocr_artifact_path": None,
                    "llm_output_artifact_path": None,
                },
            },
        )

    visual_inputs = [*bundle.selected_images, *bundle.crops]
    frame_ocr_entries: list[dict[str, Any]] = []
    image_ocr_entries: list[dict[str, Any]] = []
    ocr_visual_text: str | None = None
    ocr_image_text: str | None = None
    ocr_path = artifact_dir / "ocr.json"
    ocr_start = time.perf_counter()
    if settings.ocr_provider == "none":
        _write_json(ocr_path, {"frames": [], "post_images": [], "skipped": True, "provider": "none"})
        stage_runs.append(
            _stage_outcome(
                stage="ocr_layout",
                start=ocr_start,
                success=True,
                payload={"skipped": True, "provider": "none"},
            )
        )
    elif settings.ocr_provider != "tesseract":
        error_text = f"Unsupported OCR provider: {settings.ocr_provider}"
        warnings.append(error_text)
        nonfatal_errors.append("ocr_layout")
        _write_json(ocr_path, {"frames": [], "post_images": [], "success": False, "error_text": error_text})
        stage_runs.append(
            _stage_outcome(
                stage="ocr_layout",
                start=ocr_start,
                success=False,
                error_text=error_text,
            )
        )
    else:
        try:
            frame_ocr_entries, image_ocr_entries, ocr_visual_text, ocr_image_text = _ocr_visual_inputs(visual_inputs)
            _write_json(
                ocr_path,
                {
                    "frames": frame_ocr_entries,
                    "post_images": image_ocr_entries,
                },
            )
            stage_runs.append(
                _stage_outcome(
                    stage="ocr_layout",
                    start=ocr_start,
                    success=True,
                    payload={
                        "frame_count": len(frame_ocr_entries),
                        "post_image_count": len(image_ocr_entries),
                        "visual_text_length": len(ocr_visual_text or ""),
                        "image_text_length": len(ocr_image_text or ""),
                    },
                )
            )
        except Exception as exc:
            error_text = str(exc)
            warnings.append(f"OCR/layout extraction failed: {error_text}")
            nonfatal_errors.append("ocr_layout")
            _write_json(
                ocr_path,
                {
                    "frames": frame_ocr_entries,
                    "post_images": image_ocr_entries,
                    "success": False,
                    "error_text": error_text,
                },
            )
            stage_runs.append(
                _stage_outcome(
                    stage="ocr_layout",
                    start=ocr_start,
                    success=False,
                    error_text=error_text,
                )
            )
    artifacts.append(
        ArtifactRecord(
            kind="ocr",
            path=str(ocr_path),
            metadata={
                "frame_count": len(frame_ocr_entries),
                "post_image_count": len(image_ocr_entries),
                "visual_text_length": len(ocr_visual_text or ""),
                "image_text_length": len(ocr_image_text or ""),
            },
        )
    )

    llm_manifest = _llm_input_manifest(
        job_id=job_id,
        source_url=source_url,
        source_kind=source_kind,
        caption_text=caption_text,
        selected_images=bundle.selected_images,
        crops=bundle.crops,
        llm_images=bundle.llm_images,
        ocr_visual_text=ocr_visual_text,
        ocr_image_text=ocr_image_text,
        frame_ocr_entries=frame_ocr_entries,
        image_ocr_entries=image_ocr_entries,
        settings=settings,
    )
    llm_manifest_path = artifact_dir / "llm_input_manifest.json"
    _write_json(llm_manifest_path, llm_manifest)
    artifacts.append(
        ArtifactRecord(
            kind="llm_input_manifest",
            path=str(llm_manifest_path),
            metadata={
                "provider": settings.multimodal_llm_provider,
                "model": settings.openai_multimodal_model,
                "llm_image_count": len(bundle.llm_images),
            },
        )
    )

    reconstruction: VisualReconstruction | None = None
    llm_output_path: Path | None = None
    openai_visual_text: str | None = None
    openai_image_text: str | None = None
    llm_start = time.perf_counter()
    provider = settings.multimodal_llm_provider
    if not bundle.llm_images:
        stage_runs.append(
            _stage_outcome(
                stage="multimodal_llm_extract",
                start=llm_start,
                success=True,
                payload={"skipped": True, "provider": provider, "selected_image_count": 0},
            )
        )
    elif provider == "none":
        warnings.append("Multimodal LLM provider is not configured; visual reconstruction used OCR only.")
        stage_runs.append(
            _stage_outcome(
                stage="multimodal_llm_extract",
                start=llm_start,
                success=True,
                payload={
                    "skipped": True,
                    "provider": "none",
                    "selected_image_count": len(bundle.llm_images),
                },
            )
        )
    elif provider == "openai" and settings.max_llm_calls_per_job <= 0:
        nonfatal_errors.append("multimodal_llm_extract")
        stage_runs.append(
            _stage_outcome(
                stage="multimodal_llm_extract",
                start=llm_start,
                success=True,
                payload={
                    "skipped": True,
                    "skip_reason": "llm_call_limit_exhausted",
                    "provider": "openai",
                    "model": settings.openai_multimodal_model,
                    "selected_image_count": len(bundle.llm_images),
                },
            )
        )
    elif provider == "openai":
        try:
            llm_response = run_openai_visual_reconstruction(
                llm_input_manifest=llm_manifest,
                llm_images=bundle.llm_images,
                settings=settings,
            )
            _validate_reconstruction_sources(
                llm_response.reconstruction,
                selected_images=bundle.selected_images,
                crops=bundle.crops,
            )
            llm_output_path, _, _ = _write_success_llm_artifacts(
                artifact_dir=artifact_dir,
                llm_response=llm_response,
                artifacts=artifacts,
            )
            reconstruction = llm_response.reconstruction
            openai_visual_text = _clean_section_text(reconstruction.cleaned_frame_text)
            openai_image_text = _clean_section_text(reconstruction.cleaned_post_image_text)
            stage_runs.append(
                _stage_outcome(
                    stage="multimodal_llm_extract",
                    start=llm_start,
                    success=True,
                    payload={
                        "provider": "openai",
                        "model": settings.openai_multimodal_model,
                        "selected_image_count": len(bundle.llm_images),
                        "confidence": reconstruction.confidence,
                        "candidate_mentions_count": len(reconstruction.candidate_mentions),
                    },
                )
            )
        except Exception as exc:
            error_text = str(exc)
            warnings.append(f"OpenAI visual reconstruction failed; OCR fallback was used: {error_text}")
            nonfatal_errors.append("multimodal_llm_extract")
            llm_output_path = _write_failed_llm_artifact(
                artifact_dir=artifact_dir,
                provider="openai",
                model=settings.openai_multimodal_model,
                error_text=error_text,
                artifacts=artifacts,
            )
            stage_runs.append(
                _stage_outcome(
                    stage="multimodal_llm_extract",
                    start=llm_start,
                    success=False,
                    payload={
                        "provider": "openai",
                        "model": settings.openai_multimodal_model,
                        "selected_image_count": len(bundle.llm_images),
                    },
                    error_text=error_text,
                )
            )
    else:
        error_text = f"Unsupported multimodal LLM provider: {provider}"
        warnings.append(f"{error_text}; OCR fallback was used.")
        nonfatal_errors.append("multimodal_llm_extract")
        llm_output_path = _write_failed_llm_artifact(
            artifact_dir=artifact_dir,
            provider=provider,
            model=settings.openai_multimodal_model,
            error_text=error_text,
            artifacts=artifacts,
        )
        stage_runs.append(
            _stage_outcome(
                stage="multimodal_llm_extract",
                start=llm_start,
                success=False,
                payload={"provider": provider, "selected_image_count": len(bundle.llm_images)},
                error_text=error_text,
            )
        )

    visual_text = openai_visual_text or ocr_visual_text
    image_text = openai_image_text or ocr_image_text
    frame_text_source = "openai" if openai_visual_text else "ocr" if ocr_visual_text else "none"
    post_image_text_source = "openai" if openai_image_text else "ocr" if ocr_image_text else "none"
    candidate_mentions = (
        [candidate.model_dump(mode="json") for candidate in reconstruction.candidate_mentions]
        if reconstruction is not None
        else []
    )
    partial_cover_count = sum(
        1 for candidate in candidate_mentions if candidate.get("evidence_basis") == "partial_cover_inference"
    )
    debug = {
        "visual_reconstruction_provider": provider,
        "visual_reconstruction_model": settings.openai_multimodal_model,
        "visual_reconstruction_confidence": reconstruction.confidence if reconstruction is not None else None,
        "candidate_mentions": candidate_mentions,
        "ocr_openai_comparison": {
            "frame_text_source": frame_text_source,
            "post_image_text_source": post_image_text_source,
            "ocr_visual_text_length": len(ocr_visual_text or ""),
            "ocr_image_text_length": len(ocr_image_text or ""),
            "openai_frame_text_length": len(openai_visual_text or ""),
            "openai_post_image_text_length": len(openai_image_text or ""),
            "candidate_mentions_count": len(candidate_mentions),
            "partial_cover_inference_count": partial_cover_count,
            "ocr_artifact_path": str(ocr_path),
            "llm_output_artifact_path": str(llm_output_path) if llm_output_path is not None else None,
        },
    }
    return VisualExtractionResult(
        visual_text=visual_text,
        image_text=image_text,
        warnings=warnings,
        nonfatal_errors=nonfatal_errors,
        artifacts=artifacts,
        stage_runs=stage_runs,
        debug=debug,
    )
