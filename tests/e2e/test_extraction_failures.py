"""End-to-end: a Gemini reply the worker cannot use must fail the save, not store "no mentions".

Each scenario seeds a saved Reel, runs the real worker message handler
(`process_source_extraction_message`) against local Postgres as the `mentioned_worker` role,
and then reads the saved source back through a real API process as its owner. Gemini is a
local fake HTTP server speaking the real `generateContent` wire format, reached by the real
google-genai SDK through `GOOGLE_GEMINI_BASE_URL`, so the SDK's own response handling (for
example `response.text` being `None` on a blocked reply) is part of the test.

Only the Instagram download is stubbed: the test never contacts Instagram. The suite runs in a
database of its own (`IsolatedDatabase`), dropped afterwards, so the `make dev` worker never sees
its queue messages, including the push notifications that finishing a source queues. Each
scenario hands its extraction message straight to the handler, which archives it.

`sources` is a cache shared by every user who saves the same Reel, and only a failed source can
be retried. An unusable reply stored as done with zero items therefore tells every user of that
Reel "no mentions" for good, which is the failure these scenarios guard against.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlmodel import Session

from src.config import get_settings
from src.database import create_sql_engine
from src.extraction.download import DownloadedAssets
from src.ingestion.queue_worker import process_source_extraction_message
from src.sources.failure import SourceFailureReason, safe_source_error_message
from src.sources.models import SavedSource, Source, SourceStatus
from src.sources.queue import SOURCE_EXTRACTIONS_QUEUE, SourceExtractionMessage
from tests.e2e.fakes import FakeGemini, gemini_text_reply
from tests.e2e.harness import (
    IsolatedDatabase,
    Report,
    api_env,
    requires_local_stack,
    start_api,
    stop_api,
)

pytestmark = requires_local_stack

EXTRACTION_MODEL = FakeGemini.extraction_model
GATE_MODEL = FakeGemini.gate_model
EXTRACTION_FAILED = safe_source_error_message(SourceFailureReason.EXTRACTION_FAILED)

PROMPT_BLOCKED = {
    "promptFeedback": {"blockReason": "PROHIBITED_CONTENT"},
    "usageMetadata": {"promptTokenCount": 10, "totalTokenCount": 10},
}
CANDIDATE_BLOCKED = {"candidates": [{"finishReason": "SAFETY", "index": 0}]}
PRODUCT_MENTION = {"title": "Kindle Paperwhite", "category": "product", "confidence": 0.9}


@pytest.fixture(scope="module")
def report():
    report = Report(
        "extraction-failures",
        rerun="make dev && uv run pytest tests/e2e/test_extraction_failures.py -v",
    )
    yield report
    print(f"\nextraction failures E2E report: {report.write()}")


@pytest.fixture(scope="module")
def fake_gemini():
    fake = FakeGemini()
    fake.start()
    yield fake
    fake.stop()


@pytest.fixture(scope="module")
def database():
    database = IsolatedDatabase("mentioned_e2e_extraction_failures")
    database.create()
    yield database
    database.drop()


@pytest.fixture(scope="module")
def api(report, database):
    process, base_url = start_api(report, api_env(AUTH_MODE="dev", DATABASE_URL=database.api_url))
    yield base_url
    stop_api(process)


@pytest.fixture(scope="module")
def engines(database):
    admin = create_sql_engine(database.admin_url)
    worker = create_sql_engine(database.worker_url)
    yield admin, worker
    admin.dispose()
    worker.dispose()


@pytest.fixture
def worker_settings(monkeypatch, fake_gemini, database):
    """Configure this process as a production-shaped worker that talks to the fake Gemini."""
    env = {
        "APP_ENV": "development",
        "AUTH_MODE": "dev",
        "WORKER_DATABASE_URL": database.worker_url,
        "EXTRACTION_BACKEND": "gemini",
        "GEMINI_API_KEY": "fake-gemini-key",
        "GEMINI_USE_VERTEXAI": "false",
        "GEMINI_MODEL": EXTRACTION_MODEL,
        "GEMINI_GATE_MODEL": GATE_MODEL,
        "GEMINI_TOTAL_ATTEMPTS": "1",
        "GEMINI_TIMEOUT_SECONDS": "10",
        "RELEVANCE_GATE_MODE": "active",
        "GOOGLE_GEMINI_BASE_URL": fake_gemini.base_url,
        "SUPABASE_PROJECT_URL": "",
        "SUPABASE_SERVICE_ROLE_KEY": "",
    }
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def stub_download(monkeypatch):
    """Stand in for yt-dlp: hand the pipeline a small local video instead of a Reel."""

    def download(_url: str, output_dir: Path) -> DownloadedAssets:
        media = output_dir / "media_001.mp4"
        media.write_bytes(b"not a real video; the fake Gemini never looks at it")
        return DownloadedAssets(paths=[media], caption="Three books I loved this month")

    monkeypatch.setattr("src.extraction.pipeline.download_assets_with_metadata", download)


class SavedReels:
    """Seeds saved Reels the way the API does: a pending source plus a queue message."""

    def __init__(self, admin_engine) -> None:
        self.admin_engine = admin_engine

    def seed(self, owner_id: str) -> tuple[SourceExtractionMessage, UUID]:
        external_id = f"E2EGEM{uuid4().hex[:12]}"
        with Session(self.admin_engine) as session:
            source = Source(
                source_key=f"instagram:reel:{external_id}",
                platform="instagram",
                source_type="reel",
                external_id=external_id,
                canonical_url=f"https://www.instagram.com/reel/{external_id}/",
                status=SourceStatus.PENDING,
            )
            session.add(source)
            session.flush()
            saved = SavedSource(owner_id=UUID(owner_id), source_id=source.id)
            session.add(saved)
            msg_id = session.execute(
                text("select pgmq.send(:queue, cast(:message as jsonb), 0)"),
                {
                    "queue": SOURCE_EXTRACTIONS_QUEUE,
                    "message": json.dumps({"v": 1, "source_id": str(source.id)}),
                },
            ).scalar_one()
            session.commit()
            message = SourceExtractionMessage(msg_id=msg_id, source_id=source.id, read_count=1)
            return message, saved.id


@pytest.fixture(scope="module")
def saved_reels(engines):
    return SavedReels(engines[0])


def _save_and_process(saved_reels, engines, settings, owner_id: str) -> UUID:
    message, saved_id = saved_reels.seed(owner_id)
    process_source_extraction_message(message, engines[1], settings)
    return saved_id


def _saved_source(api: str, owner_id: str, saved_id: UUID) -> dict[str, Any]:
    response = httpx.get(
        f"{api}/v1/saved-sources/{saved_id}",
        headers={"Authorization": f"Bearer dev:{owner_id}"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


# Replies the worker cannot use. Each must end as a retryable failed save, not a done save.
UNUSABLE_REPLIES = [
    ("G1", "prompt blocked, no candidates", PROMPT_BLOCKED),
    ("G2", "candidate blocked for safety, no content", CANDIDATE_BLOCKED),
    (
        "G3",
        "JSON cut off at the output token limit",
        gemini_text_reply('{"mentions": [{"title": "Dune", "categ', finish_reason="MAX_TOKENS"),
    ),
    ("G4", "empty text", gemini_text_reply("")),
    ("G5", "top-level JSON array", gemini_text_reply("[]")),
    ("G6", "no mentions key", gemini_text_reply('{"items": []}')),
    ("G7", "mentions is not a list", gemini_text_reply('{"mentions": "none"}')),
    ("G8", "a mention is not an object", gemini_text_reply('{"mentions": ["Dune"]}')),
    (
        "G9",
        "non-numeric confidence",
        gemini_text_reply(json.dumps({"mentions": [{**PRODUCT_MENTION, "confidence": "high"}]})),
    ),
    (
        "G10",
        "confidence outside 0..1 (a percentage)",
        gemini_text_reply(json.dumps({"mentions": [{**PRODUCT_MENTION, "confidence": 95}]})),
    ),
    (
        "G11",
        "category outside book, product, and place",
        gemini_text_reply(json.dumps({"mentions": [{**PRODUCT_MENTION, "category": "movie"}]})),
    ),
]


@pytest.mark.parametrize(
    ("mode", "description", "reply"),
    UNUSABLE_REPLIES,
    ids=[mode for mode, _, _ in UNUSABLE_REPLIES],
)
def test_unusable_gemini_reply_fails_the_save(
    report,
    fake_gemini,
    api,
    engines,
    saved_reels,
    worker_settings,
    stub_download,
    mode,
    description,
    reply,
) -> None:
    with report.scenario(
        f"Unusable extraction reply: {description}",
        [mode],
        f"Fake Gemini answers the extraction call with: {json.dumps(reply)[:200]}",
    ) as scenario:
        fake_gemini.reply(extraction=reply)
        owner_id = str(uuid4())

        saved_id = _save_and_process(saved_reels, engines, worker_settings, owner_id)
        saved = _saved_source(api, owner_id, saved_id)

        scenario.check(
            "extraction call reached Gemini", True, EXTRACTION_MODEL in fake_gemini.requests
        )
        scenario.check("saved source status", "failed", saved["status"])
        scenario.check("error shown to the user", EXTRACTION_FAILED, saved["error_message"])
        scenario.check("items", [], saved["items"])


def test_genuinely_empty_reply_is_done_with_no_items(
    report, fake_gemini, api, engines, saved_reels, worker_settings, stub_download
) -> None:
    with report.scenario(
        "Gemini finds nothing in the Reel",
        ["guard: no over-correction"],
        'Fake Gemini answers {"mentions": []}',
    ) as scenario:
        fake_gemini.reply(extraction=gemini_text_reply('{"mentions": []}'))
        owner_id = str(uuid4())

        saved_id = _save_and_process(saved_reels, engines, worker_settings, owner_id)
        saved = _saved_source(api, owner_id, saved_id)

        scenario.check("saved source status", "done", saved["status"])
        scenario.check("error shown to the user", None, saved["error_message"])
        scenario.check("items", [], saved["items"])


def test_valid_reply_saves_the_mention(
    report, fake_gemini, api, engines, saved_reels, worker_settings, stub_download
) -> None:
    with report.scenario(
        "Gemini returns a valid mention",
        ["guard: happy path"],
        "Fake Gemini answers one product mention",
    ) as scenario:
        fake_gemini.reply(extraction=gemini_text_reply(json.dumps({"mentions": [PRODUCT_MENTION]})))
        owner_id = str(uuid4())

        saved_id = _save_and_process(saved_reels, engines, worker_settings, owner_id)
        saved = _saved_source(api, owner_id, saved_id)

        scenario.check("saved source status", "done", saved["status"])
        scenario.check(
            "item titles", ["Kindle Paperwhite"], [item["title"] for item in saved["items"]]
        )


def test_unusable_gate_reply_still_fails_open_to_extraction(
    report, fake_gemini, api, engines, saved_reels, worker_settings, stub_download
) -> None:
    with report.scenario(
        "Relevance gate reply is unusable",
        ["guard: gate fails open"],
        "Fake Gemini blocks the gate call and answers extraction with one product mention",
    ) as scenario:
        fake_gemini.reply(
            extraction=gemini_text_reply(json.dumps({"mentions": [PRODUCT_MENTION]})),
            gate=PROMPT_BLOCKED,
        )
        owner_id = str(uuid4())

        saved_id = _save_and_process(saved_reels, engines, worker_settings, owner_id)
        saved = _saved_source(api, owner_id, saved_id)

        scenario.check(
            "gate and extraction both called",
            [GATE_MODEL, EXTRACTION_MODEL],
            fake_gemini.requests,
        )
        scenario.check("saved source status", "done", saved["status"])
        scenario.check(
            "item titles", ["Kindle Paperwhite"], [item["title"] for item in saved["items"]]
        )
