from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from urllib.parse import urlsplit

from app.config import get_settings
from extractor.stages.download_media import download_assets
from extractor.stages.extract_audio import extract_audio
from extractor.stages.extract_entities import extract_book_candidates
from extractor.stages.fetch_html import fetch_html
from extractor.stages.normalize_url import detect_source_kind, normalize_input_url
from extractor.stages.parse_page import combine_text_fields, parse_page_metadata
from extractor.stages.probe_media import probe_media
from extractor.stages.sample_frames import sample_frames
from extractor.stages.score_candidates import score_candidates
from extractor.stages.transcribe_audio import transcribe_audio
from extractor.types import ArtifactRecord, ExtractedMentionCandidate, PipelineResult, StageOutcome, TextExtractionResult
from extractor.visual import extract_visual_text


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm"}
SUPPORTED_SOURCE_KINDS = {"instagram_reel", "instagram_post"}
GENERIC_TEXT_VALUES = {"instagram", "instagram reel", "instagram post", "instagram photo"}


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, content: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=True, indent=2), encoding="utf-8")


def _duration_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _platform_id(url: str) -> str | None:
    parts = [part for part in urlsplit(url).path.split("/") if part]
    for marker in ("reel", "p"):
        if marker in parts:
            index = parts.index(marker)
            if index + 1 < len(parts):
                return parts[index + 1]
    return None


def _clean_section_text(value: str | None) -> str | None:
    if value is None:
        return None
    lines = [" ".join(line.split()) for line in value.splitlines()]
    cleaned_lines = [line for line in lines if line]
    if not cleaned_lines:
        return None
    return "\n".join(cleaned_lines)


def _dedupe_join(values: list[str | None]) -> str | None:
    lines: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean_section_text(value)
        if not cleaned:
            continue
        for line in cleaned.splitlines():
            normalized = line.casefold()
            if normalized in GENERIC_TEXT_VALUES:
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            lines.append(line)
    if not lines:
        return None
    return "\n".join(lines)


def _caption_from_probe(probe_payload: dict | None) -> str | None:
    if probe_payload is None:
        return None
    description = probe_payload.get("description")
    if isinstance(description, str) and description.strip():
        return description.strip()
    return None


def _assemble_merged_text(
    *,
    caption_text: str | None,
    spoken_text: str | None,
    visual_text: str | None,
    image_text: str | None,
) -> str:
    sections = [
        ("Caption", caption_text),
        ("Spoken", spoken_text),
        ("Visible text", visual_text),
        ("Image text", image_text),
    ]
    rendered_sections = [
        f"{label}:\n{text.strip()}"
        for label, text in sections
        if text is not None and text.strip()
    ]
    return "\n\n".join(rendered_sections)


def _source_context_snippet(*values: str | None, max_length: int = 280) -> str | None:
    text = _dedupe_join(list(values))
    if text is None:
        return None
    return text[:max_length].rstrip()


def _candidate_mentions_from_visual_debug(debug: dict) -> list[ExtractedMentionCandidate]:
    raw_candidates = debug.get("candidate_mentions")
    if not isinstance(raw_candidates, list):
        return []
    candidates: list[ExtractedMentionCandidate] = []
    for raw_candidate in raw_candidates:
        if not isinstance(raw_candidate, dict):
            continue
        label = raw_candidate.get("label")
        if not isinstance(label, str) or not label.strip():
            continue
        category = raw_candidate.get("category")
        if not isinstance(category, str):
            category = "unknown"
        candidates.append(
            ExtractedMentionCandidate(
                label=label.strip(),
                author_or_creator=raw_candidate.get("author_or_creator")
                if isinstance(raw_candidate.get("author_or_creator"), str)
                else None,
                category=category,
                confidence=raw_candidate.get("confidence")
                if isinstance(raw_candidate.get("confidence"), int | float)
                else None,
                evidence=raw_candidate,
                evidence_text=raw_candidate.get("visible_evidence")
                if isinstance(raw_candidate.get("visible_evidence"), str)
                else None,
            )
        )
    return candidates


def _candidate_mentions_from_text(raw_text: str, *, has_probe: bool) -> list[ExtractedMentionCandidate]:
    book_candidates = score_candidates(extract_book_candidates(raw_text), has_probe=has_probe)
    return [
        ExtractedMentionCandidate(
            label=candidate.title,
            author_or_creator=candidate.author,
            category="book",
            confidence=candidate.confidence,
            evidence=candidate.evidence,
            evidence_text=candidate.evidence.get("text") if isinstance(candidate.evidence.get("text"), str) else None,
        )
        for candidate in book_candidates
    ]


def _dedupe_candidate_mentions(candidates: list[ExtractedMentionCandidate]) -> list[ExtractedMentionCandidate]:
    deduped: dict[tuple[str, str, str], ExtractedMentionCandidate] = {}
    for candidate in candidates:
        key = (
            candidate.category.casefold(),
            candidate.label.strip().casefold(),
            (candidate.author_or_creator or "").strip().casefold(),
        )
        current = deduped.get(key)
        if current is None:
            deduped[key] = candidate
            continue
        if (candidate.confidence or 0.0) > (current.confidence or 0.0):
            deduped[key] = candidate
    return sorted(deduped.values(), key=lambda item: item.confidence or 0.0, reverse=True)


def _evenly_select(paths: list[Path], max_items: int) -> list[Path]:
    if len(paths) <= max_items:
        return paths
    if max_items <= 1:
        return paths[:1]
    indexes = {
        round(index * (len(paths) - 1) / (max_items - 1))
        for index in range(max_items)
    }
    return [paths[index] for index in sorted(indexes)]


def _copy_selected_images(paths: list[Path], output_dir: Path, max_items: int) -> list[Path]:
    selected_paths = _evenly_select(paths, max_items)
    output_dir.mkdir(parents=True, exist_ok=True)
    copied_paths: list[Path] = []
    for index, source_path in enumerate(selected_paths, start=1):
        destination = output_dir / f"selected_{index:03d}{source_path.suffix.lower()}"
        shutil.copy2(source_path, destination)
        copied_paths.append(destination)
    return copied_paths


def _record_stage(
    stage_runs: list[StageOutcome],
    *,
    stage: str,
    start: float,
    success: bool,
    payload: dict | None = None,
    error_text: str | None = None,
) -> None:
    stage_runs.append(
        StageOutcome(
            stage=stage,
            success=success,
            duration_ms=_duration_ms(start),
            payload=payload,
            error_text=error_text,
        )
    )


def run_pipeline(job_id: str, source_url: str) -> PipelineResult:
    settings = get_settings()
    artifact_dir = settings.artifact_dir / job_id
    artifact_dir.mkdir(parents=True, exist_ok=True)

    stage_runs: list[StageOutcome] = []
    artifacts: list[ArtifactRecord] = []
    warnings: list[str] = []
    nonfatal_errors: list[str] = []

    normalize_start = time.perf_counter()
    normalized_url = normalize_input_url(source_url)
    source_kind = detect_source_kind(normalized_url)
    _record_stage(
        stage_runs,
        stage="normalize_url",
        start=normalize_start,
        success=True,
        payload={
            "normalized_url": normalized_url,
            "source_kind": source_kind,
            "platform_id": _platform_id(normalized_url),
        },
    )
    if source_kind not in SUPPORTED_SOURCE_KINDS:
        warnings.append("Unsupported source kind; only public Instagram Reel and post URLs are first-class v1 inputs.")

    html_text = ""
    page_metadata: dict = {}
    fetch_start = time.perf_counter()
    try:
        html_text, fetch_metadata = fetch_html(normalized_url)
        _record_stage(
            stage_runs,
            stage="fetch_html",
            start=fetch_start,
            success=True,
            payload=fetch_metadata,
        )
        source_html_path = artifact_dir / "source.html"
        _write_text(source_html_path, html_text)
        artifacts.append(ArtifactRecord(kind="source_html", path=str(source_html_path), metadata=fetch_metadata))
    except Exception as exc:
        error_text = str(exc)
        warnings.append(f"HTML fetch failed: {error_text}")
        nonfatal_errors.append("fetch_html")
        _record_stage(
            stage_runs,
            stage="fetch_html",
            start=fetch_start,
            success=False,
            error_text=error_text,
        )

    parse_start = time.perf_counter()
    if html_text:
        page_metadata = parse_page_metadata(html_text)
        _record_stage(
            stage_runs,
            stage="parse_page",
            start=parse_start,
            success=True,
            payload={"keys": sorted(page_metadata.keys())},
        )
        page_meta_path = artifact_dir / "page_meta.json"
        _write_json(page_meta_path, page_metadata)
        artifacts.append(
            ArtifactRecord(
                kind="page_meta",
                path=str(page_meta_path),
                metadata={"keys": sorted(page_metadata.keys())},
            )
        )
    else:
        _record_stage(
            stage_runs,
            stage="parse_page",
            start=parse_start,
            success=True,
            payload={"skipped": True, "reason": "fetch_html did not produce HTML"},
        )

    probe_payload: dict | None = None
    probe_start = time.perf_counter()
    if source_kind in SUPPORTED_SOURCE_KINDS:
        try:
            probe_payload = probe_media(normalized_url)
            probe_path = artifact_dir / "probe.json"
            _write_json(probe_path, probe_payload)
            artifacts.append(ArtifactRecord(kind="probe", path=str(probe_path), metadata={"extractor": "yt-dlp"}))
            _record_stage(
                stage_runs,
                stage="probe_source_media_or_images",
                start=probe_start,
                success=True,
                payload={"keys": sorted(probe_payload.keys())[:25]},
            )
        except Exception as exc:
            error_text = str(exc)
            warnings.append(f"Source probe failed: {error_text}")
            nonfatal_errors.append("probe_source_media_or_images")
            _record_stage(
                stage_runs,
                stage="probe_source_media_or_images",
                start=probe_start,
                success=False,
                error_text=error_text,
            )
    else:
        _record_stage(
            stage_runs,
            stage="probe_source_media_or_images",
            start=probe_start,
            success=True,
            payload={"skipped": True, "reason": "unsupported source kind"},
        )

    media_path: Path | None = None
    post_image_paths: list[Path] = []
    download_start = time.perf_counter()
    if source_kind in SUPPORTED_SOURCE_KINDS:
        try:
            downloaded_paths = download_assets(normalized_url, artifact_dir)
            image_paths = [path for path in downloaded_paths if path.suffix.lower() in IMAGE_SUFFIXES]
            video_paths = [path for path in downloaded_paths if path.suffix.lower() in VIDEO_SUFFIXES]
            if source_kind == "instagram_post":
                post_image_paths = image_paths
                if post_image_paths:
                    artifacts.append(
                        ArtifactRecord(
                            kind="post_images",
                            path=str(artifact_dir),
                            metadata={"image_count": len(post_image_paths), "paths": [str(path) for path in post_image_paths]},
                        )
                    )
                elif video_paths:
                    media_path = video_paths[-1]
                    warnings.append("Instagram post downloaded as video; frame OCR will be used for visible text.")
                    artifacts.append(ArtifactRecord(kind="media", path=str(media_path), metadata={"source": "yt-dlp"}))
            else:
                media_path = video_paths[-1] if video_paths else downloaded_paths[-1]
                artifacts.append(ArtifactRecord(kind="media", path=str(media_path), metadata={"source": "yt-dlp"}))
            _record_stage(
                stage_runs,
                stage="download_media_or_images",
                start=download_start,
                success=True,
                payload={
                    "downloaded_count": len(downloaded_paths),
                    "image_count": len(image_paths),
                    "video_count": len(video_paths),
                },
            )
        except Exception as exc:
            error_text = str(exc)
            warnings.append(f"Media/image download failed: {error_text}")
            nonfatal_errors.append("download_media_or_images")
            _record_stage(
                stage_runs,
                stage="download_media_or_images",
                start=download_start,
                success=False,
                error_text=error_text,
            )
    else:
        _record_stage(
            stage_runs,
            stage="download_media_or_images",
            start=download_start,
            success=True,
            payload={"skipped": True, "reason": "unsupported source kind"},
        )

    audio_path: Path | None = None
    audio_start = time.perf_counter()
    if media_path is not None and source_kind == "instagram_reel":
        try:
            audio_path = extract_audio(media_path, artifact_dir / "audio.wav")
            artifacts.append(ArtifactRecord(kind="audio", path=str(audio_path), metadata={"source": "ffmpeg"}))
            _record_stage(
                stage_runs,
                stage="extract_audio",
                start=audio_start,
                success=True,
                payload={"path": str(audio_path)},
            )
        except Exception as exc:
            error_text = str(exc)
            warnings.append(f"Audio extraction failed: {error_text}")
            nonfatal_errors.append("extract_audio")
            _record_stage(
                stage_runs,
                stage="extract_audio",
                start=audio_start,
                success=False,
                error_text=error_text,
            )
    else:
        _record_stage(
            stage_runs,
            stage="extract_audio",
            start=audio_start,
            success=True,
            payload={"skipped": True, "reason": "no reel media available"},
        )

    spoken_text: str | None = None
    transcribe_start = time.perf_counter()
    if audio_path is None:
        _record_stage(
            stage_runs,
            stage="transcribe_audio",
            start=transcribe_start,
            success=True,
            payload={
                "skipped": True,
                "provider": settings.asr_provider,
                "audio_available": False,
            },
        )
    elif settings.asr_provider == "none":
        _record_stage(
            stage_runs,
            stage="transcribe_audio",
            start=transcribe_start,
            success=True,
            payload={
                "skipped": True,
                "provider": "none",
                "audio_available": True,
            },
        )
        warnings.append("ASR provider is not configured; spoken_text was not extracted.")
    else:
        try:
            transcript = transcribe_audio(audio_path, settings)
            spoken_text = _clean_section_text(transcript.text)
            transcript_path = artifact_dir / "transcript.json"
            _write_json(
                transcript_path,
                {
                    "provider": transcript.provider,
                    "model": transcript.model,
                    "text": spoken_text,
                    "response": transcript.response,
                },
            )
            artifacts.append(
                ArtifactRecord(
                    kind="transcript",
                    path=str(transcript_path),
                    metadata={
                        "provider": transcript.provider,
                        "model": transcript.model,
                        "text_length": len(spoken_text or ""),
                    },
                )
            )
            _record_stage(
                stage_runs,
                stage="transcribe_audio",
                start=transcribe_start,
                success=True,
                payload={
                    "provider": transcript.provider,
                    "model": transcript.model,
                    "audio_available": True,
                    "spoken_text_length": len(spoken_text or ""),
                },
            )
        except Exception as exc:
            error_text = str(exc)
            warnings.append(f"Audio transcription failed: {error_text}")
            nonfatal_errors.append("transcribe_audio")
            _record_stage(
                stage_runs,
                stage="transcribe_audio",
                start=transcribe_start,
                success=False,
                payload={
                    "provider": settings.asr_provider,
                    "audio_available": True,
                },
                error_text=error_text,
            )

    sampled_frame_paths: list[Path] = []
    frame_start = time.perf_counter()
    if media_path is not None:
        try:
            frames_dir = artifact_dir / "frames"
            sampled_frame_paths = sample_frames(media_path, frames_dir)
            artifacts.append(
                ArtifactRecord(
                    kind="frames",
                    path=str(frames_dir),
                    metadata={"frame_count": len(sampled_frame_paths)},
                )
            )
            _record_stage(
                stage_runs,
                stage="sample_frames",
                start=frame_start,
                success=True,
                payload={"frame_count": len(sampled_frame_paths)},
            )
        except Exception as exc:
            error_text = str(exc)
            warnings.append(f"Frame sampling failed: {error_text}")
            nonfatal_errors.append("sample_frames")
            _record_stage(
                stage_runs,
                stage="sample_frames",
                start=frame_start,
                success=False,
                error_text=error_text,
            )
    else:
        _record_stage(
            stage_runs,
            stage="sample_frames",
            start=frame_start,
            success=True,
            payload={"skipped": True, "reason": "no media available"},
        )

    selected_frame_paths: list[Path] = []
    selected_post_image_paths: list[Path] = []
    select_start = time.perf_counter()
    if sampled_frame_paths:
        selected_frame_paths = _copy_selected_images(
            sampled_frame_paths,
            artifact_dir / "selected_frames",
            settings.max_selected_frames,
        )
        artifacts.append(
            ArtifactRecord(
                kind="selected_frames",
                path=str(artifact_dir / "selected_frames"),
                metadata={"frame_count": len(selected_frame_paths)},
            )
        )
    if post_image_paths:
        selected_post_image_paths = _evenly_select(post_image_paths, settings.max_selected_post_images)
    _record_stage(
        stage_runs,
        stage="select_images",
        start=select_start,
        success=True,
        payload={
            "selected_frame_count": len(selected_frame_paths),
            "selected_post_image_count": len(selected_post_image_paths),
        },
    )

    caption_text = _dedupe_join(
        [
            page_metadata.get("caption_text"),
            _caption_from_probe(probe_payload),
        ]
    )
    if not caption_text:
        caption_text = _dedupe_join([combine_text_fields(page_metadata)])

    visual_result = extract_visual_text(
        job_id=job_id,
        artifact_dir=artifact_dir,
        source_url=normalized_url,
        source_kind=source_kind,
        selected_frames=selected_frame_paths,
        selected_post_images=selected_post_image_paths,
        caption_text=caption_text,
        settings=settings,
    )
    stage_runs.extend(visual_result.stage_runs)
    artifacts.extend(visual_result.artifacts)
    warnings.extend(visual_result.warnings)
    nonfatal_errors.extend(visual_result.nonfatal_errors)
    visual_text = visual_result.visual_text
    image_text = visual_result.image_text

    visual_text = _clean_section_text(visual_text)
    image_text = _clean_section_text(image_text)
    merged_text = _assemble_merged_text(
        caption_text=caption_text,
        spoken_text=spoken_text,
        visual_text=visual_text,
        image_text=image_text,
    )
    if not merged_text:
        warnings.append("No useful text could be extracted from the source.")

    assemble_start = time.perf_counter()
    text_result = TextExtractionResult(
        caption_text=caption_text,
        spoken_text=spoken_text,
        visual_text=visual_text,
        image_text=image_text,
        merged_text=merged_text,
        warnings=warnings,
        debug={
            "source": {
                "normalized_url": normalized_url,
                "source_kind": source_kind,
                "platform_id": _platform_id(normalized_url),
                "source_creator": page_metadata.get("creator"),
                "source_context_snippet": _source_context_snippet(
                    caption_text,
                    page_metadata.get("title"),
                    page_metadata.get("og_title"),
                ),
            },
            "stage_count": len(stage_runs),
            "artifact_count": len(artifacts),
            "nonfatal_errors": nonfatal_errors,
            **visual_result.debug,
        },
    )
    result_path = artifact_dir / "result.json"
    _write_json(
        result_path,
        {
            "job_id": job_id,
            "source_url": normalized_url,
            "source_kind": source_kind,
            "text": {
                "caption_text": text_result.caption_text,
                "spoken_text": text_result.spoken_text,
                "visual_text": text_result.visual_text,
                "image_text": text_result.image_text,
                "merged_text": text_result.merged_text,
                "warnings": text_result.warnings,
                "debug": text_result.debug,
            },
        },
    )
    artifacts.append(ArtifactRecord(kind="text_result", path=str(result_path), metadata={"warning_count": len(warnings)}))
    _record_stage(
        stage_runs,
        stage="assemble_text_result",
        start=assemble_start,
        success=bool(merged_text),
        payload={
            "caption_text_length": len(caption_text or ""),
            "spoken_text_length": len(spoken_text or ""),
            "visual_text_length": len(visual_text or ""),
            "image_text_length": len(image_text or ""),
            "merged_text_length": len(merged_text),
            "warning_count": len(warnings),
        },
        error_text=None if merged_text else "No useful text could be extracted from the source.",
    )

    if merged_text:
        final_status = "partial" if nonfatal_errors else "succeeded"
        error_code = None
        error_message = None
    else:
        final_status = "failed"
        error_code = "no_text"
        error_message = "No useful text could be extracted from the source."

    candidate_mentions = _dedupe_candidate_mentions(
        [
            *_candidate_mentions_from_visual_debug(visual_result.debug),
            *_candidate_mentions_from_text(merged_text, has_probe=probe_payload is not None),
        ]
    )

    return PipelineResult(
        source_kind=source_kind,
        final_status=final_status,
        error_code=error_code,
        error_message=error_message,
        stage_runs=stage_runs,
        artifacts=artifacts,
        text_result=text_result,
        candidate_mentions=candidate_mentions,
    )
