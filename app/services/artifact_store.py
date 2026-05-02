from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import Settings, get_settings
from extractor.types import ArtifactRecord


@dataclass(frozen=True)
class StoredArtifact:
    kind: str
    storage_backend: str
    storage_key: str
    media_type: str | None
    byte_size: int | None
    metadata: dict | list | str | int | float | bool | None


class LocalArtifactStore:
    storage_backend = "local"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _storage_key(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.settings.data_dir.resolve()))
        except ValueError:
            return path.name

    def describe_existing(self, artifact: ArtifactRecord) -> StoredArtifact:
        path = Path(artifact.path)
        byte_size = path.stat().st_size if path.is_file() else None
        return StoredArtifact(
            kind=artifact.kind,
            storage_backend=self.storage_backend,
            storage_key=self._storage_key(path),
            media_type=None,
            byte_size=byte_size,
            metadata=artifact.metadata,
        )
