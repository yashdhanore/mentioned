from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_mentions_locally(media_paths: list[Path]) -> dict:
    logger.info("Local extraction backend received %d media file(s)", len(media_paths))
    return {"mentions": []}
