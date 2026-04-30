from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps

from app.config import Settings
from extractor.visual.models import VisualImage, VisualInputBundle, VisualRole


FULL_BBOX = (0.0, 0.0, 1.0, 1.0)
OVERLAY_BBOX = (0.0, 0.0, 1.0, 0.65)
OBJECT_BBOX = (0.0, 0.5, 1.0, 0.5)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _open_image(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).copy()


def _clamp_bbox(
    bbox_normalized: tuple[float, float, float, float],
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    x, y, box_width, box_height = bbox_normalized
    left = max(0, min(width - 1, round(x * width)))
    top = max(0, min(height - 1, round(y * height)))
    right = max(left + 1, min(width, round((x + box_width) * width)))
    bottom = max(top + 1, min(height, round((y + box_height) * height)))
    return left, top, right, bottom


def _resize_to_long_edge(image: Image.Image, max_long_edge: int) -> Image.Image:
    if max_long_edge <= 0:
        return image
    width, height = image.size
    if max(width, height) <= max_long_edge:
        return image
    resized = image.copy()
    resized.thumbnail((max_long_edge, max_long_edge), Image.Resampling.LANCZOS)
    return resized


def _entry_id(prefix: str, index: int, role: VisualRole) -> str:
    return f"{prefix}_{index:03d}_{role}"


def _full_entries(paths: Iterable[Path], *, prefix: str) -> list[VisualImage]:
    entries: list[VisualImage] = []
    source_surface = "frame" if prefix == "frame" else "post_image"
    for index, path in enumerate(paths, start=1):
        with _open_image(path) as image:
            width, height = image.size
        entry_id = _entry_id(prefix, index, "full")
        entries.append(
            VisualImage(
                id=entry_id,
                role="full",
                path=path,
                source_surface=source_surface,
                source_image_id=entry_id,
                frame_index=index if prefix == "frame" else None,
                timestamp_seconds=None,
                bbox_normalized=FULL_BBOX,
                width=width,
                height=height,
                sha256=_sha256_file(path),
            )
        )
    return entries


def _crop_entry(
    source: VisualImage,
    *,
    role: VisualRole,
    bbox_normalized: tuple[float, float, float, float],
    crops_dir: Path,
    max_long_edge: int,
) -> VisualImage:
    crop_id = source.id.removesuffix("_full") + f"_{role}"
    crop_path = crops_dir / f"{crop_id}.png"
    with _open_image(source.path) as image:
        crop = image.crop(_clamp_bbox(bbox_normalized, image.width, image.height))
        crop = _resize_to_long_edge(crop, max_long_edge)
        crop.save(crop_path)
        width, height = crop.size
    return VisualImage(
        id=crop_id,
        role=role,
        path=crop_path,
        source_surface=source.source_surface,
        source_image_id=source.id,
        frame_index=source.frame_index,
        timestamp_seconds=source.timestamp_seconds,
        bbox_normalized=bbox_normalized,
        width=width,
        height=height,
        sha256=_sha256_file(crop_path),
    )


def select_llm_images(
    selected_images: list[VisualImage],
    crops: list[VisualImage],
    *,
    max_llm_images: int,
    max_llm_crops: int,
) -> list[VisualImage]:
    llm_images: list[VisualImage] = []
    seen_full_hashes: set[str] = set()
    for image in selected_images:
        if len(llm_images) >= max_llm_images:
            return llm_images
        if image.sha256 in seen_full_hashes:
            continue
        seen_full_hashes.add(image.sha256)
        llm_images.append(image)

    seen_crop_hashes: set[tuple[str, str]] = set()
    crop_count = 0
    for crop in crops:
        if crop_count >= max_llm_crops or len(llm_images) >= max_llm_images:
            break
        key = (crop.role, crop.sha256)
        if key in seen_crop_hashes:
            continue
        seen_crop_hashes.add(key)
        llm_images.append(crop)
        crop_count += 1
    return llm_images


def generate_visual_inputs(
    *,
    selected_frames: list[Path],
    selected_post_images: list[Path],
    artifact_dir: Path,
    settings: Settings,
) -> VisualInputBundle:
    selected_images = [
        *_full_entries(selected_frames, prefix="frame"),
        *_full_entries(selected_post_images, prefix="post"),
    ]
    crops_dir = artifact_dir / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    crops: list[VisualImage] = []
    seen_crop_hashes: set[tuple[str, str]] = set()
    for selected_image in selected_images:
        for role, bbox in (("overlay", OVERLAY_BBOX), ("object", OBJECT_BBOX)):
            crop = _crop_entry(
                selected_image,
                role=role,
                bbox_normalized=bbox,
                crops_dir=crops_dir,
                max_long_edge=settings.max_image_long_edge_px,
            )
            key = (crop.role, crop.sha256)
            if key in seen_crop_hashes:
                continue
            seen_crop_hashes.add(key)
            crops.append(crop)

    llm_images = select_llm_images(
        selected_images,
        crops,
        max_llm_images=settings.max_llm_images,
        max_llm_crops=settings.max_llm_crops,
    )
    manifest = {
        "schema_version": "image_selection.v1",
        "selected_images": [entry.manifest_record() for entry in selected_images],
        "crops": [entry.manifest_record() for entry in crops],
        "llm_image_ids": [entry.id for entry in llm_images],
        "limits": {
            "max_selected_frames": settings.max_selected_frames,
            "max_selected_post_images": settings.max_selected_post_images,
            "max_llm_images": settings.max_llm_images,
            "max_llm_crops": settings.max_llm_crops,
            "max_image_long_edge_px": settings.max_image_long_edge_px,
        },
    }
    return VisualInputBundle(
        selected_images=selected_images,
        crops=crops,
        llm_images=llm_images,
        image_selection_manifest=manifest,
    )
