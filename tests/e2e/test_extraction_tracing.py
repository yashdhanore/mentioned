"""End-to-end: what the worker sends to Langfuse while it extracts a Reel, and that tracing can
never hurt a save.

Each scenario seeds a saved Reel, runs the real worker message handler
(`process_source_extraction_message`) against local Postgres as the `mentioned_worker` role, and
reads the saved source back through a real API process as its owner. Tracing runs through the
real Langfuse SDK, configured by `src.observability.configure_tracing` exactly as the worker's
`main()` does, and exports over HTTP to `FakeLangfuse`, which decodes the OTLP protobuf and the
score batches. So every check is on bytes that would have left the process for Langfuse Cloud.

Gemini and Google Books are local fakes (see `tests/e2e/fakes.py`), the download is stubbed
with a small file whose bytes the suite later looks for in everything exported, and a network
guard refuses any connection to another machine. The suite runs in a database of its own.

`FAILURE_MODES` mirrors `T1`-`T12` in the tracing implementation notes; each scenario names the
modes it covers, and the report records any mode left uncovered.
"""

from __future__ import annotations

import base64
import json
import time
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
from src.extraction.gemini import EXTRACTION_PROMPT_VERSION
from src.extraction.pricing import gemini_cost_details
from src.ingestion.queue_worker import process_source_extraction_message
from src.observability import configure_tracing, flush_tracing, shutdown_tracing
from src.sources.models import SavedSource, Source, SourceStatus
from src.sources.queue import SOURCE_EXTRACTIONS_QUEUE, SourceExtractionMessage
from tests.e2e.fakes import (
    ExportedSpan,
    FakeGemini,
    FakeGoogleBooks,
    FakeLangfuse,
    gemini_gate_reply,
    gemini_mentions_reply,
    gemini_text_reply,
)
from tests.e2e.harness import (
    IsolatedDatabase,
    NetworkGuard,
    Report,
    api_env,
    free_port,
    requires_local_stack,
    start_api,
    stop_api,
)

pytestmark = requires_local_stack

FAILURE_MODES = {
    "T1": "A processed Reel produces no extract-source trace, or its steps are not nested in it",
    "T2": "A generation lacks model, token usage, or cost, or the cost disagrees with pricing.py",
    "T3": "Media bytes, or a provider API key, are exported to Langfuse",
    "T4": "An unreachable or failing Langfuse fails the Reel, crashes the worker, or slows it",
    "T5": "Missing Langfuse keys crash the worker or export anything",
    "T6": "An unusable Gemini reply is not an ERROR in the trace, or its raw text is lost",
    "T7": "The relevance gate failing open is not visible as a WARNING with its reason",
    "T8": "A download failure is not visible in the trace",
    "T9": "Attempts at the same Reel do not share a session, or a trace carries a user id",
    "T10": "Book resolution is missing, or lacks its status, queries, and rejected candidates",
    "T11": "A trace has the wrong environment or tags, or no extraction prompt version",
    "T12": "A retried Gemini call hides the retry, or counts its cost twice",
}

DATABASE_NAME = "mentioned_e2e_extraction_tracing"
# Real, priced model names, so the suite can check cost against `src/extraction/pricing.py`.
EXTRACTION_MODEL = "gemini-3.1-flash-lite"
GATE_MODEL = "gemini-3.5-flash-lite"
GEMINI_KEY = "fake-gemini-key-e2e"
BOOKS_KEY = "fake-books-key-e2e"
PUBLIC_KEY = "pk-lf-e2e"
SECRET_KEY = "sk-lf-e2e"
ENVIRONMENT = "development"
# A Gemini reply's usage with every bucket pricing.py splits out filled in.
EXTRACTION_USAGE = {
    "promptTokenCount": 1300,
    "promptTokensDetails": [
        {"modality": "VIDEO", "tokenCount": 1000},
        {"modality": "AUDIO", "tokenCount": 200},
        {"modality": "TEXT", "tokenCount": 100},
    ],
    "candidatesTokenCount": 50,
    "thoughtsTokenCount": 10,
    "totalTokenCount": 1360,
}
EXPECTED_USAGE = {"input": 1100, "input_audio": 200, "output": 50, "output_reasoning": 10}
BLUEST_EYE = {
    "title": "The Bluest Eye",
    "author": "Toni Morrison",
    "category": "book",
    "confidence": 0.95,
}
UNLISTED_BOOK = {
    "title": "A Book No Catalog Has",
    "author": "Nobody Known",
    "category": "book",
    "confidence": 0.9,
}
BLUEST_EYE_VOLUME = {
    "kind": "books#volume",
    "id": "e2e-bluest-eye",
    "volumeInfo": {"title": "The Bluest Eye", "authors": ["Toni Morrison"], "printType": "BOOK"},
}


@pytest.fixture(scope="module")
def report():
    report = Report(
        "extraction-tracing",
        rerun="make dev && uv run pytest tests/e2e/test_extraction_tracing.py -v",
    )
    report.context["failure_modes"] = FAILURE_MODES
    report.context["fakes"] = {
        "langfuse": "FakeLangfuse decodes the SDK's real OTLP exports and score batches",
        "gemini": f"FakeGemini as {EXTRACTION_MODEL} (extraction) and {GATE_MODEL} (gate)",
        "google_books": "FakeGoogleBooks",
        "download": "stubbed; writes a marker file the suite then looks for in every export",
    }
    yield report
    covered = {mode for scenario in report.scenarios for mode in scenario["failure_modes"]}
    report.context["uncovered_failure_modes"] = sorted(set(FAILURE_MODES) - covered)
    print(f"\nextraction tracing E2E report: {report.write()}")


@pytest.fixture(scope="module")
def fake_gemini():
    fake = FakeGemini(extraction_model=EXTRACTION_MODEL, gate_model=GATE_MODEL)
    fake.start()
    yield fake
    fake.stop()


@pytest.fixture(scope="module")
def fake_books():
    fake = FakeGoogleBooks()
    fake.start()
    yield fake
    fake.stop()


@pytest.fixture(scope="module")
def fake_langfuse():
    fake = FakeLangfuse()
    fake.start()
    yield fake
    fake.stop()


@pytest.fixture(scope="module")
def database():
    database = IsolatedDatabase(DATABASE_NAME)
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


def _worker_env(fake_gemini: FakeGemini, database: IsolatedDatabase) -> dict[str, str]:
    return {
        "APP_ENV": ENVIRONMENT,
        "AUTH_MODE": "dev",
        "WORKER_DATABASE_URL": database.worker_url,
        "EXTRACTION_BACKEND": "gemini",
        "GEMINI_API_KEY": GEMINI_KEY,
        "GEMINI_USE_VERTEXAI": "false",
        "GEMINI_MODEL": EXTRACTION_MODEL,
        "GEMINI_GATE_MODEL": GATE_MODEL,
        "GEMINI_TOTAL_ATTEMPTS": "2",
        "GEMINI_TIMEOUT_SECONDS": "10",
        "RELEVANCE_GATE_MODE": "active",
        "GOOGLE_GEMINI_BASE_URL": fake_gemini.base_url,
        "GOOGLE_BOOKS_API_KEY": BOOKS_KEY,
        "SUPABASE_PROJECT_URL": "",
        "SUPABASE_SERVICE_ROLE_KEY": "",
        "LANGFUSE_TRACING_ENABLED": "true",
    }


class Tracing:
    """Configures this process's Langfuse client the way the worker's `main()` does."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.monkeypatch = monkeypatch

    def configure(
        self, *, base_url: str | None, public_key: str = PUBLIC_KEY, secret_key: str = SECRET_KEY
    ):
        # Each configuration uses its own public key: the SDK keeps one client per key for
        # the life of the process, so a reused key would bring back an earlier base URL.
        for name, value in {
            "LANGFUSE_PUBLIC_KEY": public_key if base_url else "",
            "LANGFUSE_SECRET_KEY": secret_key if base_url else "",
            "LANGFUSE_BASE_URL": base_url or "",
        }.items():
            self.monkeypatch.setenv(name, value)
        get_settings.cache_clear()
        settings = get_settings()
        configure_tracing(settings, flush_interval=0.2)
        return settings


@pytest.fixture
def tracing(monkeypatch, fake_gemini, fake_books, fake_langfuse, database):
    for name, value in _worker_env(fake_gemini, database).items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr("src.extraction.google_books.GOOGLE_BOOKS_API", fake_books.api_url)
    monkeypatch.setattr("src.extraction.gemini.RETRY_DELAYS_SECONDS", [0, 0, 0])
    NetworkGuard().install(monkeypatch)
    tracing = Tracing(monkeypatch)
    yield tracing
    shutdown_tracing()
    get_settings.cache_clear()


class StubDownload:
    """Stands in for yt-dlp with a small file of unique bytes, and can fail on demand."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.media_bytes = f"E2E-MEDIA-BYTES-{uuid4().hex}".encode()
        self.error: str | None = None
        monkeypatch.setattr("src.extraction.pipeline.download_assets_with_metadata", self)

    def __call__(self, _url: str, output_dir: Path) -> DownloadedAssets:
        if self.error:
            raise RuntimeError(self.error)
        media = output_dir / "media_001.mp4"
        media.write_bytes(self.media_bytes)
        return DownloadedAssets(
            paths=[media],
            caption="Two books I loved this month",
            source_creator_handle="e2e.reader",
        )


@pytest.fixture
def download(monkeypatch):
    return StubDownload(monkeypatch)


class SavedReels:
    """Seeds saved Reels the way the API does: a pending source plus a queue message."""

    def __init__(self, admin_engine) -> None:
        self.admin_engine = admin_engine

    def seed(self, owner_id: str) -> tuple[SourceExtractionMessage, UUID, UUID]:
        external_id = f"E2ETRACE{uuid4().hex[:10]}"
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
            session.commit()
            return self.requeue(source.id), saved.id, source.id

    def requeue(self, source_id: UUID) -> SourceExtractionMessage:
        """Put a source back to pending with a fresh queue message, like a retry save."""
        with Session(self.admin_engine) as session:
            session.execute(
                text("update sources set status = 'pending' where id = :id"), {"id": source_id}
            )
            msg_id = session.execute(
                text("select pgmq.send(:queue, cast(:message as jsonb), 0)"),
                {
                    "queue": SOURCE_EXTRACTIONS_QUEUE,
                    "message": json.dumps({"v": 1, "source_id": str(source_id)}),
                },
            ).scalar_one()
            session.commit()
        return SourceExtractionMessage(msg_id=msg_id, source_id=source_id, read_count=1)


@pytest.fixture(scope="module")
def saved_reels(engines):
    return SavedReels(engines[0])


def _process(message, engines, settings) -> float:
    started = time.monotonic()
    process_source_extraction_message(message, engines[1], settings)
    return time.monotonic() - started


def _saved_source(api: str, owner_id: str, saved_id: UUID) -> dict[str, Any]:
    response = httpx.get(
        f"{api}/v1/saved-sources/{saved_id}",
        headers={"Authorization": f"Bearer dev:{owner_id}"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def _trace(fake_langfuse: FakeLangfuse, source_id: UUID) -> list[ExportedSpan]:
    """Every exported span of the newest extract-source trace for `source_id`."""
    flush_tracing()
    spans = fake_langfuse.spans_in_session(str(source_id))
    roots = [span for span in spans if span.name == "extract-source"]
    if not roots:
        return []
    trace_id = roots[-1].trace_id
    with fake_langfuse.lock:
        return [span for span in fake_langfuse.spans if span.trace_id == trace_id]


def _one(spans: list[ExportedSpan], name: str) -> ExportedSpan | None:
    matches = [span for span in spans if span.name == name]
    return matches[0] if len(matches) == 1 else None


def _names(spans: list[ExportedSpan]) -> list[str]:
    return sorted(span.name for span in spans)


def _rounded(values: dict[str, Any] | None) -> dict[str, float] | None:
    if values is None:
        return None
    return {key: round(value, 12) for key, value in values.items()}


def test_a_successful_extraction_is_one_nested_priced_trace(
    report, fake_gemini, fake_books, fake_langfuse, api, engines, saved_reels, tracing, download
) -> None:
    with report.scenario(
        "Successful extraction with one confirmed and one unconfirmed book",
        ["T1", "T2", "T3", "T9", "T10", "T11"],
        "Gemini returns two books with full token usage; Books confirms one and knows nothing "
        "about the other; Langfuse is up",
    ) as scenario:
        settings = tracing.configure(base_url=fake_langfuse.base_url)
        fake_gemini.reply(
            extraction=gemini_mentions_reply([BLUEST_EYE, UNLISTED_BOOK], usage=EXTRACTION_USAGE),
            gate=gemini_gate_reply("relevant", "a book cover"),
        )
        fake_books.volumes("intitle:The Bluest Eye+inauthor:Toni Morrison", [BLUEST_EYE_VOLUME])
        owner_id = str(uuid4())
        message, saved_id, source_id = saved_reels.seed(owner_id)

        _process(message, engines, settings)
        saved = _saved_source(api, owner_id, saved_id)
        spans = _trace(fake_langfuse, source_id)

        scenario.check("saved source status", "done", saved["status"])
        root = _one(spans, "extract-source")
        scenario.check("one extract-source root", True, root is not None)
        assert root is not None
        scenario.check("root has no parent", None, root.parent_span_id)
        scenario.check(
            "steps in the trace",
            sorted(
                [
                    "extract-source",
                    "download-media",
                    "assess-relevance",
                    "extract-mentions",
                    "resolve-book",
                    "resolve-book",
                ]
            ),
            _names(spans),
        )
        scenario.check(
            "every step is a direct child of the root",
            True,
            all(span.parent_span_id == root.span_id for span in spans if span is not root),
        )
        scenario.check(
            "observation types",
            {
                "extract-source": "span",
                "download-media": "span",
                "assess-relevance": "generation",
                "extract-mentions": "generation",
                "resolve-book": "retriever",
            },
            {span.name: span.type for span in spans},
        )

        extraction = _one(spans, "extract-mentions")
        assert extraction is not None
        scenario.check("extraction model", EXTRACTION_MODEL, extraction.model)
        scenario.check("extraction usage", EXPECTED_USAGE, extraction.usage)
        expected_cost = gemini_cost_details(EXTRACTION_MODEL, EXPECTED_USAGE)
        assert expected_cost is not None
        expected_cost["total"] = sum(expected_cost.values())
        scenario.check(
            "extraction cost matches pricing.py", _rounded(expected_cost), _rounded(extraction.cost)
        )
        scenario.check(
            "extraction prompt version",
            EXTRACTION_PROMPT_VERSION,
            extraction.metadata.get("prompt_version"),
        )
        scenario.check(
            "extraction output is the parsed mentions",
            ["The Bluest Eye", "A Book No Catalog Has"],
            [mention["title"] for mention in (extraction.output or {}).get("mentions", [])],
        )
        gate = _one(spans, "assess-relevance")
        assert gate is not None
        scenario.check("gate model", GATE_MODEL, gate.model)
        scenario.check(
            "gate output", {"verdict": "relevant", "reason": "a book cover"}, gate.output
        )
        scenario.check("gate cost recorded", True, bool(gate.cost and gate.cost.get("total")))

        resolutions = {span.input["title"]: span for span in spans if span.name == "resolve-book"}
        confirmed = resolutions["The Bluest Eye"]
        unconfirmed = resolutions["A Book No Catalog Has"]
        scenario.check("confirmed book status", "resolved", confirmed.output["status"])
        scenario.check(
            "confirmed book volume", "e2e-bluest-eye", confirmed.output["book"]["volume_id"]
        )
        scenario.check(
            "confirmed book queries",
            ["intitle:The Bluest Eye+inauthor:Toni Morrison"],
            confirmed.metadata.get("queries"),
        )
        scenario.check("unconfirmed book status", "not_found", unconfirmed.output["status"])
        scenario.check(
            "unconfirmed book tried the title alone after the combined query",
            2,
            len(unconfirmed.metadata.get("queries") or []),
        )

        scenario.check(
            "root output",
            {
                "outcome": "done",
                "stored": True,
                "titles": ["The Bluest Eye", "A Book No Catalog Has"],
            },
            {
                "outcome": root.output["outcome"],
                "stored": root.output["stored"],
                "titles": [item["title"] for item in root.output["items"]],
            },
        )
        scenario.check(
            "catalog match per item",
            [True, False],
            [i["catalog_match"] for i in root.output["items"]],
        )
        scenario.check(
            "every span in the source's session",
            True,
            all(s.session_id == str(source_id) for s in spans),
        )
        scenario.check("no span carries a user id", True, all(s.user_id is None for s in spans))
        scenario.check("root trace name", "extract-source", root.trace_name)
        scenario.check("root tags", ["instagram", "reel"], sorted(root.tags))
        scenario.check("environment", ENVIRONMENT, root.environment)
        scenario.check(
            "outcome score",
            [{"name": "extraction-outcome", "value": "done", "dataType": "CATEGORICAL"}],
            [
                {key: score.get(key) for key in ("name", "value", "dataType")}
                for score in fake_langfuse.scores_for_trace(root.trace_id)
            ],
        )

        sent = fake_langfuse.everything_sent()
        scenario.check("media bytes never sent", False, download.media_bytes in sent)
        scenario.check(
            "base64 media never sent", False, base64.b64encode(download.media_bytes) in sent
        )
        scenario.check("Gemini key never sent", False, GEMINI_KEY.encode() in sent)
        scenario.check("Books key never sent", False, BOOKS_KEY.encode() in sent)
        basic_auth = "Basic " + base64.b64encode(f"{PUBLIC_KEY}:{SECRET_KEY}".encode()).decode()
        scenario.check(
            "SDK authenticated with the configured keys",
            True,
            basic_auth in set(fake_langfuse.authorizations),
        )


def test_an_unusable_reply_is_an_error_with_its_raw_text(
    report, fake_gemini, fake_langfuse, api, engines, saved_reels, tracing, download
) -> None:
    truncated = '{"mentions": [{"title": "Dune", "categ'
    with report.scenario(
        "Gemini reply cut off at the token limit",
        ["T6"],
        "Gemini answers extraction with truncated JSON and finish reason MAX_TOKENS",
    ) as scenario:
        settings = tracing.configure(base_url=fake_langfuse.base_url, public_key=PUBLIC_KEY + "-6")
        fake_gemini.reply(extraction=gemini_text_reply(truncated, finish_reason="MAX_TOKENS"))
        owner_id = str(uuid4())
        message, saved_id, source_id = saved_reels.seed(owner_id)

        _process(message, engines, settings)
        saved = _saved_source(api, owner_id, saved_id)
        spans = _trace(fake_langfuse, source_id)
        root = _one(spans, "extract-source")
        extraction = _one(spans, "extract-mentions")
        assert root is not None
        assert extraction is not None

        scenario.check("saved source status", "failed", saved["status"])
        scenario.check("extraction level", "ERROR", extraction.level)
        scenario.check(
            "extraction status names the parse failure",
            True,
            (extraction.status_message or "").startswith(
                "GeminiResponseError: Gemini returned invalid JSON"
            ),
        )
        scenario.check("raw reply kept as output", truncated, extraction.output)
        scenario.check("finish reason", "MAX_TOKENS", extraction.metadata.get("finish_reason"))
        scenario.check("root level", "ERROR", root.level)
        scenario.check("root outcome", "failed", root.output["outcome"])
        scenario.check(
            "outcome score",
            ["failed"],
            [score.get("value") for score in fake_langfuse.scores_for_trace(root.trace_id)],
        )


def test_a_gate_that_fails_open_is_a_warning(
    report, fake_gemini, fake_langfuse, api, engines, saved_reels, tracing, download
) -> None:
    with report.scenario(
        "Relevance gate reply blocked",
        ["T7"],
        "Gemini blocks the gate call and answers extraction with one book",
    ) as scenario:
        settings = tracing.configure(base_url=fake_langfuse.base_url, public_key=PUBLIC_KEY + "-7")
        fake_gemini.reply(
            extraction=gemini_mentions_reply([BLUEST_EYE]),
            gate={"promptFeedback": {"blockReason": "PROHIBITED_CONTENT"}},
        )
        owner_id = str(uuid4())
        message, saved_id, source_id = saved_reels.seed(owner_id)

        _process(message, engines, settings)
        saved = _saved_source(api, owner_id, saved_id)
        spans = _trace(fake_langfuse, source_id)
        gate = _one(spans, "assess-relevance")
        assert gate is not None

        scenario.check("saved source status", "done", saved["status"])
        scenario.check("gate level", "WARNING", gate.level)
        scenario.check("gate status", "failed open: empty response", gate.status_message)
        scenario.check("gate verdict", "uncertain", gate.output["verdict"])
        scenario.check("gate block reason", "PROHIBITED_CONTENT", gate.metadata.get("block_reason"))
        scenario.check("extraction still ran", True, _one(spans, "extract-mentions") is not None)


def test_a_retry_of_a_failed_download_joins_the_same_session(
    report, fake_gemini, fake_langfuse, api, engines, saved_reels, tracing, download
) -> None:
    with report.scenario(
        "Download fails, then the Reel is retried and succeeds",
        ["T8", "T9"],
        "The stub download raises on the first attempt and works on the second",
    ) as scenario:
        settings = tracing.configure(base_url=fake_langfuse.base_url, public_key=PUBLIC_KEY + "-8")
        fake_gemini.reply(extraction=gemini_mentions_reply([BLUEST_EYE]))
        download.error = "ERROR: [Instagram] login required"
        owner_id = str(uuid4())
        message, saved_id, source_id = saved_reels.seed(owner_id)

        _process(message, engines, settings)
        first = _trace(fake_langfuse, source_id)
        scenario.check(
            "first attempt status", "failed", _saved_source(api, owner_id, saved_id)["status"]
        )
        failed_download = _one(first, "download-media")
        assert failed_download is not None
        scenario.check("download level", "ERROR", failed_download.level)
        scenario.check(
            "download status",
            "RuntimeError: ERROR: [Instagram] login required",
            failed_download.status_message,
        )
        scenario.check("no model was called", ["download-media", "extract-source"], _names(first))

        download.error = None
        _process(saved_reels.requeue(source_id), engines, settings)
        second = _trace(fake_langfuse, source_id)
        scenario.check(
            "second attempt status", "done", _saved_source(api, owner_id, saved_id)["status"]
        )
        roots = [
            s for s in fake_langfuse.spans_in_session(str(source_id)) if s.name == "extract-source"
        ]
        scenario.check(
            "two traces in the source's session", 2, len({root.trace_id for root in roots})
        )
        scenario.check(
            "attempts are separate traces", True, first[0].trace_id != second[0].trace_id
        )


def test_a_retried_gemini_call_shows_the_retry_and_bills_once(
    report, fake_gemini, fake_langfuse, api, engines, saved_reels, tracing, download
) -> None:
    with report.scenario(
        "Gemini rate-limits the extraction once, then answers",
        ["T12"],
        "The extraction model answers 429 once, then two books with full usage",
    ) as scenario:
        settings = tracing.configure(base_url=fake_langfuse.base_url, public_key=PUBLIC_KEY + "-12")
        fake_gemini.reply(extraction=gemini_mentions_reply([BLUEST_EYE], usage=EXTRACTION_USAGE))
        fake_gemini.fail_next(EXTRACTION_MODEL, 429)
        owner_id = str(uuid4())
        message, saved_id, source_id = saved_reels.seed(owner_id)

        _process(message, engines, settings)
        spans = _trace(fake_langfuse, source_id)
        extraction = _one(spans, "extract-mentions")
        retry = _one(spans, "retry-gemini-call")
        assert extraction is not None

        scenario.check(
            "saved source status", "done", _saved_source(api, owner_id, saved_id)["status"]
        )
        scenario.check("extraction requests", 2, fake_gemini.requests.count(EXTRACTION_MODEL))
        scenario.check("one retry event", True, retry is not None)
        assert retry is not None
        scenario.check("retry is inside the extraction", extraction.span_id, retry.parent_span_id)
        scenario.check("retry level", "WARNING", retry.level)
        scenario.check("retry names the 429", True, "429" in (retry.status_message or ""))
        scenario.check("usage counted once", EXPECTED_USAGE, extraction.usage)


@pytest.mark.parametrize("outage", ["unreachable", "503"])
def test_a_langfuse_outage_never_hurts_a_save(
    report, fake_gemini, fake_langfuse, api, engines, saved_reels, tracing, download, outage
) -> None:
    with report.scenario(
        f"Langfuse outage ({outage})",
        ["T4"],
        "Tracing exports to a closed port" if outage == "unreachable" else "Langfuse answers 503",
    ) as scenario:
        down = None
        if outage == "503":
            down = FakeLangfuse(status=503)
            down.start()
            base_url = down.base_url
        else:
            base_url = f"http://127.0.0.1:{free_port()}"
        try:
            settings = tracing.configure(base_url=base_url, public_key=f"{PUBLIC_KEY}-{outage}")
            fake_gemini.reply(extraction=gemini_mentions_reply([BLUEST_EYE]))
            owner_id = str(uuid4())
            message, saved_id, _source_id = saved_reels.seed(owner_id)

            seconds = _process(message, engines, settings)
            saved = _saved_source(api, owner_id, saved_id)

            scenario.check("saved source status", "done", saved["status"])
            scenario.check("item titles", ["The Bluest Eye"], [i["title"] for i in saved["items"]])
            scenario.check("extraction was not held up by the export", True, seconds < 5)
            shutdown_tracing()
            if down is not None:
                scenario.check("the SDK did try to export", True, bool(down.bodies))
        finally:
            if down is not None:
                down.stop()


def test_missing_keys_export_nothing(
    report, fake_gemini, fake_langfuse, api, engines, saved_reels, tracing, download
) -> None:
    with report.scenario(
        "No Langfuse keys configured",
        ["T5"],
        "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are empty, the way tests and a fresh "
        "clone run",
    ) as scenario:
        settings = tracing.configure(base_url=None)
        fake_gemini.reply(extraction=gemini_mentions_reply([BLUEST_EYE]))
        owner_id = str(uuid4())
        message, saved_id, source_id = saved_reels.seed(owner_id)
        sent_before = len(fake_langfuse.bodies)

        _process(message, engines, settings)
        saved = _saved_source(api, owner_id, saved_id)
        flush_tracing()

        scenario.check("tracing is off", False, settings.langfuse.enabled)
        scenario.check("saved source status", "done", saved["status"])
        scenario.check("nothing exported", sent_before, len(fake_langfuse.bodies))
        scenario.check(
            "no spans for the source", [], fake_langfuse.spans_in_session(str(source_id))
        )
