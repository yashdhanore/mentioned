"""End-to-end: a Gemini reply the worker cannot use must fail the save, not store "no mentions".

Each scenario seeds a saved Reel, runs the real worker message handler
(`process_source_extraction_message`) against local Postgres as the `mentioned_worker` role,
and then reads the saved source back through a real API process as its owner. Gemini is a
local fake HTTP server speaking the real `generateContent` wire format, reached by the real
google-genai SDK through `GOOGLE_GEMINI_BASE_URL`, so the SDK's own response handling (for
example `response.text` being `None` on a blocked reply) is part of the test.

Only the Instagram download is stubbed: the test never contacts Instagram. Each queue message
is sent with a visibility delay and handed straight to the handler, which archives it, so the
`make dev` worker never picks it up.

`sources` is a cache shared by every user who saves the same Reel, and only a failed source can
be retried. An unusable reply stored as done with zero items therefore tells every user of that
Reel "no mentions" for good, which is the failure these scenarios guard against.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlmodel import Session, create_engine, select

from src.config import get_settings
from src.extraction.download import DownloadedAssets
from src.ingestion.queue_worker import process_source_extraction_message
from src.sources.failure import SourceFailureReason, safe_source_error_message
from src.sources.models import SavedSource, Source, SourceItem, SourceStatus
from src.sources.queue import SOURCE_EXTRACTIONS_QUEUE, SourceExtractionMessage
from tests.e2e.harness import (
    WORKER_DATABASE_URL,
    Report,
    admin_database_url,
    api_env,
    free_port,
    requires_local_stack,
    start_api,
    stop_api,
)

pytestmark = requires_local_stack

EXTRACTION_MODEL = "fake-extraction-model"
GATE_MODEL = "fake-gate-model"
EXTRACTION_FAILED = safe_source_error_message(SourceFailureReason.EXTRACTION_FAILED)
# Long enough that the `make dev` worker never sees the message before this test archives it.
QUEUE_DELAY_SECONDS = 300


def _text_reply(text: str, finish_reason: str = "STOP") -> dict[str, Any]:
    return {
        "candidates": [
            {
                "content": {"role": "model", "parts": [{"text": text}]},
                "finishReason": finish_reason,
                "index": 0,
            }
        ],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15},
    }


PROMPT_BLOCKED = {
    "promptFeedback": {"blockReason": "PROHIBITED_CONTENT"},
    "usageMetadata": {"promptTokenCount": 10, "totalTokenCount": 10},
}
CANDIDATE_BLOCKED = {"candidates": [{"finishReason": "SAFETY", "index": 0}]}
RELEVANT_GATE = _text_reply(json.dumps({"verdict": "relevant", "reason": "fake gate"}))
PRODUCT_MENTION = {"title": "Kindle Paperwhite", "category": "product", "confidence": 0.9}


class FakeGemini:
    """A local stand-in for the Gemini API that answers each model with a set reply."""

    def __init__(self) -> None:
        self.replies: dict[str, dict[str, Any]] = {}
        self.requests: list[str] = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                # Path shape: /v1beta/models/<model>:generateContent
                model = self.path.split("/models/", 1)[-1].split(":", 1)[0]
                fake.requests.append(model)
                body = json.dumps(fake.replies.get(model, {"error": "no reply set"})).encode()
                self.send_response(200 if model in fake.replies else 500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", free_port()), Handler)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def reply(self, *, extraction: dict[str, Any], gate: dict[str, Any] = RELEVANT_GATE) -> None:
        self.replies = {EXTRACTION_MODEL: extraction, GATE_MODEL: gate}
        self.requests = []


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
    fake.thread.start()
    yield fake
    fake.server.shutdown()


@pytest.fixture(scope="module")
def api(report):
    process, base_url = start_api(report, api_env(AUTH_MODE="dev"))
    yield base_url
    stop_api(process)


@pytest.fixture(scope="module")
def engines():
    admin = create_engine(admin_database_url())
    worker = create_engine(WORKER_DATABASE_URL.replace("postgresql://", "postgresql+psycopg://"))
    yield admin, worker
    admin.dispose()
    worker.dispose()


@pytest.fixture
def worker_settings(monkeypatch, fake_gemini):
    """Configure this process as a production-shaped worker that talks to the fake Gemini."""
    env = {
        "APP_ENV": "development",
        "AUTH_MODE": "dev",
        "WORKER_DATABASE_URL": WORKER_DATABASE_URL,
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
    """Seeds saved Reels the way the API does (a pending source plus a queue message) and
    removes them after the module."""

    def __init__(self, admin_engine) -> None:
        self.admin_engine = admin_engine
        self.source_ids: list[UUID] = []
        self.message_ids: list[int] = []

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
                text("select pgmq.send(:queue, cast(:message as jsonb), :delay)"),
                {
                    "queue": SOURCE_EXTRACTIONS_QUEUE,
                    "message": json.dumps({"v": 1, "source_id": str(source.id)}),
                    "delay": QUEUE_DELAY_SECONDS,
                },
            ).scalar_one()
            session.commit()
            self.source_ids.append(source.id)
            self.message_ids.append(msg_id)
            message = SourceExtractionMessage(msg_id=msg_id, source_id=source.id, read_count=1)
            return message, saved.id

    def cleanup(self) -> None:
        with Session(self.admin_engine) as session:
            for msg_id in self.message_ids:
                session.execute(
                    text("select pgmq.delete(:queue, cast(:msg_id as bigint))"),
                    {"queue": SOURCE_EXTRACTIONS_QUEUE, "msg_id": msg_id},
                )
            for source_id in self.source_ids:
                for model in (SourceItem, SavedSource):
                    for row in session.exec(select(model).where(model.source_id == source_id)):
                        session.delete(row)
                session.flush()
                source = session.get(Source, source_id)
                if source is not None:
                    session.delete(source)
            session.commit()


@pytest.fixture(scope="module")
def saved_reels(engines):
    reels = SavedReels(engines[0])
    yield reels
    reels.cleanup()


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
        _text_reply('{"mentions": [{"title": "Dune", "categ', finish_reason="MAX_TOKENS"),
    ),
    ("G4", "empty text", _text_reply("")),
    ("G5", "top-level JSON array", _text_reply("[]")),
    ("G6", "no mentions key", _text_reply('{"items": []}')),
    ("G7", "mentions is not a list", _text_reply('{"mentions": "none"}')),
    ("G8", "a mention is not an object", _text_reply('{"mentions": ["Dune"]}')),
    (
        "G9",
        "non-numeric confidence",
        _text_reply(json.dumps({"mentions": [{**PRODUCT_MENTION, "confidence": "high"}]})),
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
        fake_gemini.reply(extraction=_text_reply('{"mentions": []}'))
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
        fake_gemini.reply(extraction=_text_reply(json.dumps({"mentions": [PRODUCT_MENTION]})))
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
            extraction=_text_reply(json.dumps({"mentions": [PRODUCT_MENTION]})),
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
