"""End-to-end: the product's core loop, save -> extract -> revisit, against the real local stack.

A user saves a Reel through a real API process (dev sign-in, the `mentioned_api` role, so RLS
applies), the real worker loop body (`src.worker._run_queue_worker_iteration`) takes the queue
message as the `mentioned_worker` role and extracts it, and the user reads the result back
through the API, the way the app does.

The suite runs in a database of its own on the local Postgres (`IsolatedDatabase`), migrated
by Alembic like production. The API queues every new save with no delay, and in the `make dev`
database the running `make dev` worker would take that message and try to download the fake
Reel from Instagram; in this database only the suite's worker reads the queue. No production
code has a test seam for this.

Providers are faked at their boundary (see `tests/e2e/fakes.py`): yt-dlp is a fake executable
first on PATH, Gemini a local server reached through `GOOGLE_GEMINI_BASE_URL`, and Google Books
a local server that `GOOGLE_BOOKS_API` is pointed at. A network guard refuses any connection
this process tries to open to another machine. Places have no provider yet, so none is faked.

`FAILURE_MODES` lists every way the loop can fail that the suite checks, written before the
tests; each scenario names the modes it covers, and the report records any mode left uncovered.
"""

from __future__ import annotations

import json
import shutil
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlmodel import Session

from src.config import get_settings
from src.database import check_worker_database_role, create_sql_engine
from src.sources.failure import SourceFailureReason, safe_source_error_message
from src.sources.models import SavedSource, Source, SourceStatus
from src.timeutils import utc_now
from src.worker import _run_queue_worker_iteration
from tests.e2e.fakes import (
    FakeGemini,
    FakeGoogleBooks,
    FakeYtDlp,
    gemini_gate_reply,
    gemini_mentions_reply,
)
from tests.e2e.harness import (
    IsolatedDatabase,
    NetworkGuard,
    Report,
    api_env,
    requires_local_stack,
    start_api,
    stop_api,
)

pytestmark = requires_local_stack

FAILURE_MODES = {
    "L1": "A new Reel is saved but no extraction is queued, or the first response is wrong",
    "L2": "Saving the same Reel again (or a share-sheet variant of its URL) duplicates it",
    "L3": "Concurrent saves of a new Reel (double tap, two users) fail or duplicate it",
    "L4": "Invalid input is accepted or leaves rows or queue messages behind",
    "L5": "An API that requires HTTPS accepts an http URL",
    "L6": "A desktop /reels/<code>/ link is rejected or saved as a different Reel than "
    "/reel/<code>/",
    "Q1": "More than 3 new saves in a minute are accepted",
    "Q2": "More than 25 saves in a day are accepted",
    "Q3": "More than 5 Reels processing at once are accepted",
    "Q4": "Quotas refuse a re-save of an already saved Reel, or count another user's saves",
    "Q5": "Retrying a failed Reel bypasses the rate limit, or a refused retry re-queues it",
    "X1": "A confirmed book is not attached to its catalog entry, or Books is asked wrongly",
    "X2": "A book the catalog cannot confirm is attached to the wrong entry or dropped",
    "X3": "A Books outage fails the Reel or drops the mention",
    "X4": "Mentions are lost, reordered, or renumbered; untitled mentions are kept",
    "X5": "The creator handle from the Reel metadata is not shown on revisit",
    "X6": "The relevance gate says irrelevant but the extraction still runs, or it shows failed",
    "X7": "A download failure is stored as done, or still calls Gemini",
    "X8": "The same book in two Reels creates two catalog rows",
    "X9": "The database refuses the extracted items and the worker run crashes, or leaves "
    "the Reel processing or its message queued",
    "C1": "A second user saving a done Reel re-extracts it or sees different items",
    "C2": "Two users saving a pending Reel get two extractions or different results",
    "C3": "Saving a failed Reel again does not retry it, or other savers do not see the retry",
    "C4": "A first save of a Reel that failed for someone else returns that failure unretried",
    "V1": "Detail responses miss fields or map source statuses wrongly",
    "V2": "The list is not newest first, or `limit` is ignored or accepts out-of-range values",
    "V3": "One user sees or deletes another user's saved sources, in the API or through RLS",
    "V4": "Deleting a saved source affects other users, or a re-save after delete re-extracts",
    "V5": "Deleting while the Reel is processing breaks the worker or brings the Reel back",
}

DATABASE_NAME = "mentioned_e2e_save_extract_revisit"
BOOKS_API_KEY = "fake-books-key"
EXTRACTION = FakeGemini.extraction_model
GATE = FakeGemini.gate_model
DOWNLOAD_FAILED = safe_source_error_message(SourceFailureReason.DOWNLOAD_FAILED)
UNEXPECTED_ERROR = safe_source_error_message(SourceFailureReason.UNEXPECTED_ERROR)
# What yt-dlp prints when Instagram refuses an anonymous download.
INSTAGRAM_REFUSED = (
    "[Instagram] Requested content is not available, rate-limit reached or login required"
)
# The production defaults, pinned so the developer's `.env` cannot change them.
QUOTA_ENV = {
    "MAX_JOB_CREATE_BURST_PER_MINUTE": "3",
    "MAX_JOBS_CREATED_PER_DAY": "25",
    "MAX_ACTIVE_JOBS_PER_USER": "5",
}
MAX_WORKER_ITERATIONS = 50
LOCK_WAIT_TIMEOUT_SECONDS = 10
SAVED_SOURCE_FIELDS = {
    "id",
    "source_id",
    "source_key",
    "status",
    "source_url",
    "thumbnail_url",
    "source_creator_handle",
    "error_message",
    "skip_reason",
    "created_at",
    "items",
}
ITEM_FIELDS = {
    "id",
    "book_id",
    "title",
    "author",
    "category",
    "confidence",
    "google_books_url",
    "cover_image_url",
    "place_id",
    "formatted_address",
    "latitude",
    "longitude",
    "maps_url",
    "position",
}
PLACE_FIELDS = ("place_id", "formatted_address", "latitude", "longitude", "maps_url")


def _volume(title: str, authors: list[str], subtitle: str | None = None) -> dict[str, Any]:
    """A Books `volumes` item as the API returns it, with a unique id per call."""
    volume_id = f"e2e-{uuid4().hex[:10]}"
    info: dict[str, Any] = {
        "title": title,
        "authors": authors,
        "printType": "BOOK",
        "language": "en",
        "imageLinks": {
            "smallThumbnail": f"http://books.google.com/books/content?id={volume_id}&zoom=5",
            "thumbnail": f"http://books.google.com/books/content?id={volume_id}&zoom=1",
        },
        "infoLink": f"https://books.google.com/books?id={volume_id}&hl=en",
    }
    if subtitle:
        info["subtitle"] = subtitle
    return {
        "kind": "books#volume",
        "id": volume_id,
        "etag": f"etag-{volume_id}",
        "selfLink": f"https://www.googleapis.com/books/v1/volumes/{volume_id}",
        "volumeInfo": info,
    }


def _books_query(title: str, author: str) -> str:
    return f"intitle:{title}+inauthor:{author}"


class Reel:
    def __init__(self, shortcode: str) -> None:
        self.shortcode = shortcode
        self.url = f"https://www.instagram.com/reel/{shortcode}/"
        self.source_key = f"instagram:reel:{shortcode}"


class User:
    """One app user, signed in with the dev bearer token, calling the real API."""

    def __init__(self, api_url: str) -> None:
        self.id = str(uuid4())
        self.api_url = api_url
        self.headers = {"Authorization": f"Bearer dev:{self.id}"}

    def post_body(self, body: Any) -> httpx.Response:
        return httpx.post(
            f"{self.api_url}/v1/saved-sources", json=body, headers=self.headers, timeout=30
        )

    def save(self, url: str) -> httpx.Response:
        return self.post_body({"url": url})

    def list(self, **params: Any) -> httpx.Response:
        return httpx.get(
            f"{self.api_url}/v1/saved-sources", params=params, headers=self.headers, timeout=30
        )

    def get(self, saved_id: str) -> httpx.Response:
        return httpx.get(
            f"{self.api_url}/v1/saved-sources/{saved_id}", headers=self.headers, timeout=30
        )

    def delete(self, saved_id: str) -> httpx.Response:
        return httpx.delete(
            f"{self.api_url}/v1/saved-sources/{saved_id}", headers=self.headers, timeout=30
        )

    def saved(self, saved_id: str) -> dict[str, Any]:
        response = self.get(saved_id)
        response.raise_for_status()
        return response.json()

    def listed(self) -> list[tuple[str, str]]:
        response = self.list()
        response.raise_for_status()
        return [(saved["id"], saved["status"]) for saved in response.json()]


class Loop:
    """What a scenario needs: users, fake Reels, the worker, and a view of the database."""

    def __init__(
        self,
        *,
        api_url: str,
        admin_engine,
        worker_engine,
        settings,
        gemini: FakeGemini,
        books: FakeGoogleBooks,
        yt_dlp: FakeYtDlp,
    ) -> None:
        self.api_url = api_url
        self.admin_engine = admin_engine
        self.worker_engine = worker_engine
        self.settings = settings
        self.gemini = gemini
        self.books = books
        self.yt_dlp = yt_dlp
        self._books_start = len(books.requests)

    def user(self) -> User:
        return User(self.api_url)

    def reel(
        self,
        mentions: list[dict[str, Any]] | None = None,
        *,
        gate: dict[str, Any] | None = None,
        creator: str = "e2e.reader",
        download_error: str | None = None,
    ) -> Reel:
        """Register a fake Reel with yt-dlp and Gemini; nothing exists in the database yet."""
        reel = Reel(f"E2ELoop{uuid4().hex[:10]}")
        self.yt_dlp.add(
            reel.shortcode,
            caption=f"Three picks I loved this month ({reel.shortcode})",
            creator=creator,
            error=download_error,
        )
        self.gemini.reply_for_reel(
            reel.shortcode, extraction=gemini_mentions_reply(mentions or []), gate=gate
        )
        return reel

    def books_requests(self) -> list[dict[str, str | None]]:
        """Books requests made since this scenario started."""
        return self.books.requests[self._books_start :]

    def run_worker(self) -> int:
        """Run the worker's loop body until no extraction message is visible; return how
        many iterations that took."""
        for iteration in range(MAX_WORKER_ITERATIONS):
            if self.visible_messages() == 0:
                return iteration
            _run_queue_worker_iteration(self.settings, self.worker_engine)
        raise AssertionError(f"worker still had messages after {MAX_WORKER_ITERATIONS} runs")

    def _scalar(self, sql: str, **params: Any) -> Any:
        with self.admin_engine.connect() as connection:
            return connection.execute(text(sql), params).scalar_one()

    def visible_messages(self) -> int:
        return self._scalar(
            "select count(*) from pgmq.q_extract_sources where vt <= clock_timestamp()"
        )

    def source(self, reel: Reel) -> dict[str, Any] | None:
        with self.admin_engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        "select id, status, error_message, skip_reason from sources "
                        "where source_key = :key"
                    ),
                    {"key": reel.source_key},
                )
                .mappings()
                .first()
            )
        return dict(row) if row else None

    def source_count(self, reel: Reel) -> int:
        return self._scalar(
            "select count(*) from sources where source_key = :key", key=reel.source_key
        )

    def item_count(self, reel: Reel) -> int:
        return self._scalar(
            "select count(*) from source_items i join sources s on s.id = i.source_id "
            "where s.source_key = :key",
            key=reel.source_key,
        )

    def messages_sent(self, reel: Reel) -> int:
        """Extraction messages ever sent for the Reel: still queued plus archived."""
        return self._scalar(
            "select (select count(*) from pgmq.q_extract_sources q join sources s "
            "on s.id::text = q.message->>'source_id' where s.source_key = :key) "
            "+ (select count(*) from pgmq.a_extract_sources a join sources s "
            "on s.id::text = a.message->>'source_id' where s.source_key = :key)",
            key=reel.source_key,
        )

    def messages_queued(self, reel: Reel) -> int:
        return self._scalar(
            "select count(*) from pgmq.q_extract_sources q join sources s "
            "on s.id::text = q.message->>'source_id' where s.source_key = :key",
            key=reel.source_key,
        )

    def saved_count(self, user: User) -> int:
        return self._scalar(
            "select count(*) from saved_sources where owner_id = cast(:owner as uuid)",
            owner=user.id,
        )

    def book_rows(self, volume: dict[str, Any]) -> list[str]:
        with self.admin_engine.connect() as connection:
            rows = connection.execute(
                text("select id::text from books where provider_volume_id = :volume_id"),
                {"volume_id": volume["id"]},
            ).all()
        return [row[0] for row in rows]

    def wait_for_blocked_saves(self, locktype: str, count: int) -> None:
        """Wait until `count` API connections wait on a lock of `locktype`."""
        deadline = time.monotonic() + LOCK_WAIT_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            waiting = self._scalar(
                "select count(*) from pg_locks l join pg_stat_activity a on a.pid = l.pid "
                "where not l.granted and l.locktype = :locktype "
                "and a.datname = current_database() and a.usename = 'mentioned_api'",
                locktype=locktype,
            )
            if waiting == count:
                return
            time.sleep(0.05)
        raise RuntimeError(f"{count} saves never waited on a {locktype} lock")

    def push_messages_handled(self, reel: Reel) -> int:
        """Push notification messages for the Reel that the worker's push drain archived."""
        return self._scalar(
            "select count(*) from pgmq.a_push_notifications a join sources s "
            "on s.id::text = a.message->>'source_id' where s.source_key = :key",
            key=reel.source_key,
        )

    def place_rows(self) -> int:
        return self._scalar("select count(*) from places")

    @contextmanager
    def another_save_in_flight(self, reel: Reel) -> Iterator[Any]:
        """Another user's save of a new `reel`, stopped just before it commits: the source row
        is inserted and queued, so a concurrent save of the same Reel waits on it. The caller
        commits the yielded connection to let that save finish.

        Its saved_sources row is left out: that insert would hold a lock that a scenario's
        table lock on saved_sources would then wait for."""
        with self.admin_engine.connect() as connection:
            source_id = connection.execute(
                text(
                    "insert into sources (source_key, platform, source_type, external_id, "
                    "canonical_url) values (:key, 'instagram', 'reel', :code, :url) returning id"
                ),
                {"key": reel.source_key, "code": reel.shortcode, "url": reel.url},
            ).scalar_one()
            connection.execute(
                text("select pgmq.send('extract_sources', cast(:message as jsonb), 0)"),
                {"message": json.dumps({"v": 1, "source_id": str(source_id)})},
            )
            yield connection

    def unregistered_reels(self, count: int) -> list[Reel]:
        """Reels that exist only as seeded rows; the worker never gets a message for them."""
        return [Reel(f"E2ESeed{uuid4().hex[:10]}") for _ in range(count)]

    def seed_saved(
        self, user: User, reels: list[Reel], *, status: SourceStatus, age: timedelta
    ) -> None:
        """Saves made `age` ago, inserted directly, to put a user at a quota edge."""
        created = utc_now() - age
        with Session(self.admin_engine) as session:
            for reel in reels:
                source = Source(
                    source_key=reel.source_key,
                    platform="instagram",
                    source_type="reel",
                    external_id=reel.shortcode,
                    canonical_url=reel.url,
                    status=status,
                    created_at=created,
                    updated_at=created,
                )
                session.add(source)
                session.flush()
                session.add(
                    SavedSource(owner_id=UUID(user.id), source_id=source.id, created_at=created)
                )
            session.commit()


def _loop_api_env(database: IsolatedDatabase, **overrides: str) -> dict[str, str]:
    settings = {
        "AUTH_MODE": "dev",
        "DATABASE_URL": database.api_url,
        "SOURCE_REQUIRE_HTTPS": "false",
        **QUOTA_ENV,
    }
    return api_env(**{**settings, **overrides})


@pytest.fixture(scope="module")
def report():
    report = Report(
        "save-extract-revisit",
        rerun="make dev && uv run pytest tests/e2e/test_save_extract_revisit.py -v",
    )
    report.context["failure_modes"] = FAILURE_MODES
    yield report
    covered = {mode for scenario in report.scenarios for mode in scenario["failure_modes"]}
    report.context["failure_modes_without_a_scenario"] = sorted(set(FAILURE_MODES) - covered)
    print(f"\nsave -> extract -> revisit E2E report: {report.write()}")


@pytest.fixture(scope="module")
def database(report):
    database = IsolatedDatabase(DATABASE_NAME)
    database.create()
    report.context["database"] = {
        "name": database.name,
        "why": "the `make dev` worker polls the queue in the `postgres` database, not this one",
        "migrated_with": "alembic upgrade head",
    }
    yield database
    database.drop()


@pytest.fixture(scope="module")
def admin_engine(database):
    engine = create_sql_engine(database.admin_url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def worker_engine(database, report):
    engine = create_sql_engine(database.worker_url)
    # The same refusal of a superuser or BYPASSRLS role the production worker applies.
    check_worker_database_role(engine, require_postgres=True)
    with engine.connect() as connection:
        report.context["worker_database_role"] = connection.execute(
            text("select current_user")
        ).scalar_one()
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def api(report, database):
    process, base_url = start_api(report, _loop_api_env(database))
    report.context["api"] = {"auth_mode": "dev", "database_role": "mentioned_api", **QUOTA_ENV}
    yield base_url
    stop_api(process)


@pytest.fixture(scope="module")
def fake_gemini():
    fake = FakeGemini()
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
def fake_yt_dlp(tmp_path_factory):
    return FakeYtDlp(tmp_path_factory.mktemp("fake-yt-dlp"))


@pytest.fixture
def loop(
    monkeypatch,
    report,
    api,
    admin_engine,
    worker_engine,
    database,
    fake_gemini,
    fake_books,
    fake_yt_dlp,
):
    """Configure this process as a production-shaped worker that only talks to the fakes."""
    guard = NetworkGuard()
    guard.install(monkeypatch)
    fake_yt_dlp.install(monkeypatch)
    worker_env = {
        "APP_ENV": "development",
        "AUTH_MODE": "dev",
        "WORKER_DATABASE_URL": database.worker_url,
        "EXTRACTION_BACKEND": "gemini",
        "GEMINI_API_KEY": "fake-gemini-key",
        "GEMINI_USE_VERTEXAI": "false",
        "GEMINI_MODEL": EXTRACTION,
        "GEMINI_GATE_MODEL": GATE,
        "GEMINI_TOTAL_ATTEMPTS": "1",
        "GEMINI_TIMEOUT_SECONDS": "10",
        "GOOGLE_GEMINI_BASE_URL": fake_gemini.base_url,
        "GOOGLE_BOOKS_API_KEY": BOOKS_API_KEY,
        "RELEVANCE_GATE_MODE": "active",
        "MEDIA_DOWNLOAD_FORMAT": "",
        "WORKER_QUEUE_MAX_POLL_SECONDS": "1",
        # Thumbnail storage is out of scope: the fake Reels have no thumbnail.
        "SUPABASE_PROJECT_URL": "",
        "SUPABASE_SERVICE_ROLE_KEY": "",
    }
    for name, value in worker_env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr("src.extraction.google_books.GOOGLE_BOOKS_API", fake_books.api_url)
    get_settings.cache_clear()
    report.context["providers"] = {
        "instagram download": f"fake yt-dlp at {shutil.which('yt-dlp')}",
        "gemini": f"FakeGemini at {fake_gemini.base_url} via GOOGLE_GEMINI_BASE_URL",
        "google books": f"FakeGoogleBooks at {fake_books.api_url} via GOOGLE_BOOKS_API",
        "google places": "none: find_google_place_sync has no provider yet",
    }
    assert shutil.which("yt-dlp") == fake_yt_dlp.executable

    loop = Loop(
        api_url=api,
        admin_engine=admin_engine,
        worker_engine=worker_engine,
        settings=get_settings(),
        gemini=fake_gemini,
        books=fake_books,
        yt_dlp=fake_yt_dlp,
    )
    yield loop
    # Leave the queue empty so the next scenario starts clean.
    loop.run_worker()
    get_settings.cache_clear()
    report.context["connections_refused_by_network_guard"] = report.context.get(
        "connections_refused_by_network_guard", []
    ) + list(guard.blocked)
    assert guard.blocked == [], f"code under test tried to reach: {guard.blocked}"


def _at_once(calls: list[Callable[[], httpx.Response]]) -> list[httpx.Response]:
    """Start every call at the same moment, like a double tap or two users at once."""
    barrier = threading.Barrier(len(calls))
    responses: list[httpx.Response | None] = [None] * len(calls)

    def run(index: int, call: Callable[[], httpx.Response]) -> None:
        barrier.wait()
        responses[index] = call()

    threads = [threading.Thread(target=run, args=pair) for pair in enumerate(calls)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert all(response is not None for response in responses)
    return responses  # type: ignore[return-value]


def _error(response: httpx.Response) -> tuple[int, str | None]:
    return response.status_code, response.json().get("error_code")


def _item_view(item: dict[str, Any], *fields: str) -> dict[str, Any]:
    view = {field: item[field] for field in fields}
    if "confidence" in view and view["confidence"] is not None:
        view["confidence"] = round(view["confidence"], 6)
    return view


# Save


def test_saved_reel_is_extracted_and_revisited(report, loop) -> None:
    with report.scenario(
        "A user saves a Reel with a book, a product, and a place, then revisits it",
        ["L1", "V1", "X1", "X4", "X5"],
        "A new Reel shared with a tracking param; Gemini finds a book, a product, an untitled "
        "mention, and a place; Books confirms the book",
    ) as scenario:
        volume = _volume("Project Hail Mary", ["Andy Weir"])
        query = _books_query("Project Hail Mary", "Andy Weir")
        loop.books.volumes(query, [volume])
        reel = loop.reel(
            [
                {
                    "title": "Project Hail Mary",
                    "author": "Andy Weir",
                    "category": "book",
                    "confidence": 0.9,
                },
                {"title": "Kindle Paperwhite", "category": "product", "confidence": 0.8},
                {"title": "", "category": "product", "confidence": 0.5},
                {
                    "title": "Shakespeare and Company",
                    "category": "place",
                    "confidence": 0.7,
                    "location_hint": "Paris",
                },
            ],
            creator="e2e.bookclub",
        )
        user = loop.user()

        response = user.save(f"{reel.url}?igsh=e2eshare")
        scenario.check("save status", 202, response.status_code)
        saved = response.json()
        scenario.check("response fields", SAVED_SOURCE_FIELDS, set(saved))
        scenario.check("status right after saving", "processing", saved["status"])
        # The app parses dates with Date.parse, which reads a timestamp without an offset as
        # local time.
        scenario.check("created_at is UTC with a Z", True, saved["created_at"].endswith("Z"))
        scenario.check("canonical source url", reel.url, saved["source_url"])
        scenario.check("source key", reel.source_key, saved["source_key"])
        scenario.check("items before extraction", [], saved["items"])
        scenario.check("extraction messages queued", 1, loop.messages_queued(reel))
        scenario.check("list while processing", [(saved["id"], "processing")], user.listed())

        scenario.check("worker iterations to drain the queue", 1, loop.run_worker())

        detail = user.saved(saved["id"])
        scenario.check("status after extraction", "done", detail["status"])
        scenario.check(
            "error and skip reason", (None, None), (detail["error_message"], detail["skip_reason"])
        )
        scenario.check(
            "creator handle from the Reel metadata", "e2e.bookclub", detail["source_creator_handle"]
        )
        scenario.check("thumbnail (the fake Reel has none)", None, detail["thumbnail_url"])
        scenario.check(
            "saved id and date unchanged",
            (saved["id"], saved["created_at"]),
            (detail["id"], detail["created_at"]),
        )
        items = detail["items"]
        scenario.check("item fields", [ITEM_FIELDS] * 3, [set(item) for item in items])
        scenario.check(
            "items in extraction order, the untitled one dropped",
            [
                ("Project Hail Mary", "book", 0),
                ("Kindle Paperwhite", "product", 1),
                ("Shakespeare and Company", "place", 2),
            ],
            [(item["title"], item["category"], item["position"]) for item in items],
        )
        book, product, place = items
        scenario.check(
            "book attached to its confirmed catalog entry",
            {
                "book_id": loop.book_rows(volume)[0],
                "author": "Andy Weir",
                "google_books_url": volume["volumeInfo"]["infoLink"],
                "cover_image_url": volume["volumeInfo"]["imageLinks"]["thumbnail"].replace(
                    "http://", "https://", 1
                ),
                "confidence": 0.95,
            },
            _item_view(
                book, "book_id", "author", "google_books_url", "cover_image_url", "confidence"
            ),
        )
        scenario.check(
            "book has no place details",
            dict.fromkeys(PLACE_FIELDS),
            _item_view(book, *PLACE_FIELDS),
        )
        scenario.check(
            "Books asked once, by title and author, with the API key",
            [
                {
                    "path": FakeGoogleBooks.PATH,
                    "q": query,
                    "key": BOOKS_API_KEY,
                    "maxResults": "5",
                }
            ],
            loop.books_requests(),
        )
        scenario.check(
            "product stored as extracted",
            {"book_id": None, "author": None, "google_books_url": None, "confidence": 0.8},
            _item_view(product, "book_id", "author", "google_books_url", "confidence"),
        )
        scenario.check(
            "place stored without place details (no places provider yet)",
            {**dict.fromkeys(PLACE_FIELDS), "confidence": 0.7},
            _item_view(place, *PLACE_FIELDS, "confidence"),
        )
        scenario.check("place rows written", 0, loop.place_rows())
        scenario.check(
            "Gemini calls for this Reel",
            [GATE, EXTRACTION],
            loop.gemini.models_called_for(reel.shortcode),
        )
        scenario.check(
            "yt-dlp calls for this Reel",
            ["metadata", "download"],
            [call["mode"] for call in loop.yt_dlp.calls(reel.shortcode)],
        )
        scenario.check(
            "push notification queued on completion and handled by the worker",
            1,
            loop.push_messages_handled(reel),
        )
        scenario.check("list after extraction", [(saved["id"], "done")], user.listed())
        scenario.check(
            "listed items match the detail", [items], [s["items"] for s in user.list().json()]
        )


def test_saving_the_same_reel_again_returns_the_same_save(report, loop) -> None:
    with report.scenario(
        "A user saves the same Reel again, through several share-sheet URL variants",
        ["L2"],
        "One Reel saved by URL, then by variants with tracking params, http, no www, an "
        "upper-case host, whitespace, and no trailing slash, before and after extraction",
    ) as scenario:
        reel = loop.reel(
            [{"title": "Moleskine Notebook", "category": "product", "confidence": 0.9}]
        )
        user = loop.user()
        variants = [
            f"{reel.url}?igsh=abc123&utm_source=ig_web_copy_link",
            f"http://instagram.com/reel/{reel.shortcode}",
            f"  https://WWW.INSTAGRAM.COM/reel/{reel.shortcode}/  ",
            f"https://www.instagram.com/reel/{reel.shortcode}",
        ]

        first = user.save(reel.url)
        scenario.check("first save status", 202, first.status_code)
        saved_id = first.json()["id"]
        again = [user.save(url) for url in variants]
        scenario.check(
            "every variant returns the same save",
            [(202, saved_id, "processing")] * len(variants),
            [(r.status_code, r.json()["id"], r.json()["status"]) for r in again],
        )
        scenario.check("saved sources for the user", 1, loop.saved_count(user))
        scenario.check("source rows for the Reel", 1, loop.source_count(reel))
        scenario.check("extraction messages sent", 1, loop.messages_sent(reel))

        loop.run_worker()
        after = user.save(variants[0])
        scenario.check(
            "saving again once done",
            (202, saved_id, "done"),
            (after.status_code, after.json()["id"], after.json()["status"]),
        )
        scenario.check("extraction messages sent after all saves", 1, loop.messages_sent(reel))
        scenario.check(
            "Gemini calls", [GATE, EXTRACTION], loop.gemini.models_called_for(reel.shortcode)
        )


def test_desktop_reels_link_saves_the_same_reel(report, loop) -> None:
    with report.scenario(
        "A user saves a Reel from the desktop Reels tab, then from a share link",
        ["L6"],
        "The same Reel saved as instagram.com/reels/<code>/ and then as /reel/<code>/",
    ) as scenario:
        reel = loop.reel([{"title": "Leuchtturm1917", "category": "product", "confidence": 0.9}])
        user = loop.user()

        desktop = user.save(f"https://www.instagram.com/reels/{reel.shortcode}/")
        scenario.check("desktop link status", 202, desktop.status_code)
        shared = user.save(reel.url)
        scenario.check(
            "the share link returns the same save",
            (202, desktop.json()["id"]),
            (shared.status_code, shared.json()["id"]),
        )
        scenario.check("source rows for the Reel", 1, loop.source_count(reel))
        scenario.check("extraction messages sent", 1, loop.messages_sent(reel))
        loop.run_worker()
        scenario.check(
            "extracted from the canonical Reel URL",
            ("done", ["Leuchtturm1917"]),
            (
                user.saved(desktop.json()["id"])["status"],
                [item["title"] for item in user.saved(desktop.json()["id"])["items"]],
            ),
        )


def test_double_tap_saves_the_reel_once(report, loop) -> None:
    with report.scenario(
        "A user double-taps save on a new Reel",
        ["L3"],
        "Three rounds, each a fresh user sending two saves of a fresh Reel at the same moment",
    ) as scenario:
        rounds = []
        for _ in range(3):
            reel = loop.reel()
            user = loop.user()
            responses = _at_once([lambda u=user, r=reel: u.save(r.url)] * 2)
            rounds.append(
                {
                    "statuses": [response.status_code for response in responses],
                    "same saved id": len({response.json().get("id") for response in responses})
                    == 1,
                    "saved sources": loop.saved_count(user),
                    "source rows": loop.source_count(reel),
                    "messages sent": loop.messages_sent(reel),
                }
            )
        expected = {
            "statuses": [202, 202],
            "same saved id": True,
            "saved sources": 1,
            "source rows": 1,
            "messages sent": 1,
        }
        scenario.check("every round", [expected] * 3, rounds)


def test_two_users_saving_a_new_reel_at_once_share_one_source(report, loop) -> None:
    with report.scenario(
        "Two users save the same new Reel at the same moment",
        ["L3"],
        "Three rounds, each two fresh users saving a fresh Reel at the same moment",
    ) as scenario:
        rounds = []
        for _ in range(3):
            reel = loop.reel()
            users = [loop.user(), loop.user()]
            responses = _at_once([lambda u=user, r=reel: u.save(r.url) for user in users])
            rounds.append(
                {
                    "statuses": [response.status_code for response in responses],
                    "distinct saved ids": len(
                        {response.json().get("id") for response in responses}
                    ),
                    "same source": len(
                        {response.json().get("source_id") for response in responses}
                    ),
                    "source rows": loop.source_count(reel),
                    "messages sent": loop.messages_sent(reel),
                }
            )
        expected = {
            "statuses": [202, 202],
            "distinct saved ids": 2,
            "same source": 1,
            "source rows": 1,
            "messages sent": 1,
        }
        scenario.check("every round", [expected] * 3, rounds)


def test_save_that_loses_the_race_for_a_new_reel_uses_the_winners_source(report, loop) -> None:
    with report.scenario(
        "A user saves a new Reel while another user's save of it is committing",
        ["L3"],
        "User one's save is held mid-transaction (source inserted and queued, not committed); "
        "user two saves, waits on that row, and is released when user one's save commits",
    ) as scenario:
        reel = loop.reel()
        user = loop.user()
        responses: list[httpx.Response] = []
        with loop.another_save_in_flight(reel) as other_save:
            thread = threading.Thread(target=lambda: responses.append(user.save(reel.url)))
            thread.start()
            loop.wait_for_blocked_saves("transactionid", 1)
            other_save.commit()
            thread.join(timeout=60)

        scenario.check(
            "user two's save",
            [(202, "processing")],
            [(r.status_code, r.json().get("status")) for r in responses],
        )
        scenario.check("source rows for the Reel", 1, loop.source_count(reel))
        scenario.check("saved sources for user two", 1, loop.saved_count(user))
        scenario.check("extraction messages sent (user one's only)", 1, loop.messages_sent(reel))


def test_double_tap_while_another_user_saves_the_same_new_reel(report, loop) -> None:
    with report.scenario(
        "A user double-taps save on a new Reel while another user is saving it",
        ["L3"],
        "User one's save is held mid-transaction (source inserted, not committed) while user "
        "two sends two saves; database locks then release them in the order that makes both "
        "of user two's requests retry at once",
    ) as scenario:
        reel = loop.reel()
        user = loop.user()
        responses: list[httpx.Response] = []
        with loop.another_save_in_flight(reel) as other_save, loop.admin_engine.connect() as held:
            # Holds every saved_sources insert back, so both of user two's retries reach
            # their insert before either of them commits.
            held.execute(text("lock table saved_sources in share mode"))

            threads = [
                threading.Thread(target=lambda: responses.append(user.save(reel.url)))
                for _ in range(2)
            ]
            for thread in threads:
                thread.start()
            # Both saves wait on user one's uncommitted source row.
            loop.wait_for_blocked_saves("transactionid", 2)
            other_save.commit()
            # Both lost the source_key race, retried, and now wait to insert their save.
            loop.wait_for_blocked_saves("relation", 2)
            held.commit()
            for thread in threads:
                thread.join(timeout=60)

        scenario.check("both saves", [202, 202], sorted(r.status_code for r in responses))
        scenario.check("same saved id", 1, len({r.json().get("id") for r in responses}))
        scenario.check("saved sources for user two", 1, loop.saved_count(user))
        scenario.check("extraction messages sent", 1, loop.messages_sent(reel))


INVALID_URLS = [
    ("not a URL", "three books I loved"),
    ("ftp scheme", "ftp://www.instagram.com/reel/E2EBadScheme/"),
    ("javascript scheme", "javascript:alert(1)"),
    ("another platform", "https://www.tiktok.com/@reader/video/7300000000000000000"),
    ("lookalike host with a suffix", "https://instagram.com.e2e.example/reel/E2ELookalike/"),
    ("lookalike host with a prefix", "https://notinstagram.com/reel/E2ELookalike/"),
    ("Instagram profile", "https://www.instagram.com/e2e.reader/"),
    ("Instagram story", "https://www.instagram.com/stories/e2e.reader/3300000000000000000/"),
    ("Reel path without an id", "https://www.instagram.com/reel/"),
]


def test_invalid_urls_are_rejected_and_store_nothing(report, loop, database) -> None:
    with report.scenario(
        "A user saves something that is not an Instagram Reel or post",
        ["L4", "L5"],
        "Invalid URLs and request bodies against the dev API, then an http URL against an API "
        "with SOURCE_REQUIRE_HTTPS=true",
    ) as scenario:
        user = loop.user()
        scenario.check(
            "invalid URLs",
            {name: (400, "invalid_source_url") for name, _ in INVALID_URLS},
            {name: _error(user.save(url)) for name, url in INVALID_URLS},
        )
        bodies = {
            "empty url": {"url": ""},
            "url over 2048 characters": {"url": "https://www.instagram.com/reel/" + "a" * 2048},
            "missing url": {},
            "extra field": {"url": "https://www.instagram.com/reel/E2EExtra/", "owner_id": user.id},
            "url is not a string": {"url": ["https://www.instagram.com/reel/E2EList/"]},
        }
        scenario.check(
            "invalid request bodies",
            dict.fromkeys(bodies, (422, "validation_error")),
            {name: _error(user.post_body(body)) for name, body in bodies.items()},
        )
        scenario.check("user's list", [], user.listed())
        scenario.check("saved sources for the user", 0, loop.saved_count(user))
        scenario.check("queue messages", 0, loop.visible_messages())

        process, https_api = start_api(report, _loop_api_env(database, SOURCE_REQUIRE_HTTPS="true"))
        try:
            https_user = User(https_api)
            reel = loop.reel()
            http_url = reel.url.replace("https://", "http://", 1)
            scenario.check(
                "http URL on an API that requires HTTPS",
                (400, "invalid_source_url"),
                _error(https_user.save(http_url)),
            )
            scenario.check("nothing stored for the http URL", 0, loop.source_count(reel))
            scenario.check("https URL on the same API", 202, https_user.save(reel.url).status_code)
        finally:
            stop_api(process)


# Quotas


def test_burst_of_new_saves_is_rate_limited(report, loop) -> None:
    with report.scenario(
        "A user saves a fourth new Reel within a minute",
        ["Q1", "Q4"],
        "Burst limit 3 per minute; a second user then saves the refused Reel",
    ) as scenario:
        user = loop.user()
        reels = [loop.reel() for _ in range(4)]
        statuses = [user.save(reel.url).status_code for reel in reels[:3]]
        scenario.check("first three saves", [202, 202, 202], statuses)
        scenario.check("fourth save", (429, "rate_limited"), _error(user.save(reels[3].url)))
        scenario.check("nothing stored for the refused Reel", 0, loop.source_count(reels[3]))
        scenario.check("saved sources for the user", 3, loop.saved_count(user))
        scenario.check(
            "re-saving an already saved Reel at the limit",
            202,
            user.save(reels[0].url).status_code,
        )
        other = loop.user()
        scenario.check(
            "another user saves the refused Reel", 202, other.save(reels[3].url).status_code
        )


TWO_HOURS = timedelta(hours=2)
TWO_DAYS = timedelta(days=2)


def test_daily_save_limit(report, loop) -> None:
    with report.scenario(
        "Users near the daily limit save a new Reel, and retry a failed one",
        ["Q2", "Q4", "Q5"],
        "User one has 25 saves from two hours ago; user two has 24, plus a Reel from two days "
        "ago that keeps failing, which they retry twice",
    ) as scenario:
        user = loop.user()
        seeded = loop.unregistered_reels(25)
        loop.seed_saved(user, seeded, status=SourceStatus.DONE, age=TWO_HOURS)
        reel = loop.reel()
        scenario.check("26th save today", (429, "quota_exceeded"), _error(user.save(reel.url)))
        scenario.check("nothing stored for the refused Reel", 0, loop.source_count(reel))
        resave = user.save(seeded[0].url)
        scenario.check(
            "re-saving a Reel saved earlier today",
            (202, "done"),
            (resave.status_code, resave.json().get("status")),
        )

        retrying = loop.user()
        loop.seed_saved(
            retrying, loop.unregistered_reels(24), status=SourceStatus.DONE, age=TWO_HOURS
        )
        failing = loop.reel(download_error=INSTAGRAM_REFUSED)
        loop.seed_saved(retrying, [failing], status=SourceStatus.FAILED, age=TWO_DAYS)
        first_retry = retrying.save(failing.url)
        scenario.check(
            "retry with 24 saves today",
            (202, "processing"),
            (first_retry.status_code, first_retry.json().get("status")),
        )
        loop.run_worker()
        scenario.check(
            "retry with 24 saves and 1 retry today",
            (429, "quota_exceeded"),
            _error(retrying.save(failing.url)),
        )
        scenario.check(
            "the refused retry leaves the Reel failed and unqueued",
            ("failed", 0),
            (loop.source(failing)["status"], loop.messages_queued(failing)),
        )


def test_active_processing_limit(report, loop) -> None:
    with report.scenario(
        "A user with 5 Reels still processing saves another, and retries a failed one",
        ["Q3", "Q4", "V1"],
        "3 pending and 2 processing saves from two hours ago plus a failed one from two days "
        "ago, inserted directly; then a new save, a retry, and a second user saving the Reel",
    ) as scenario:
        user = loop.user()
        pending, processing = loop.unregistered_reels(3), loop.unregistered_reels(2)
        loop.seed_saved(user, pending, status=SourceStatus.PENDING, age=TWO_HOURS)
        loop.seed_saved(user, processing, status=SourceStatus.PROCESSING, age=TWO_HOURS)
        failed = loop.reel(download_error=INSTAGRAM_REFUSED)
        loop.seed_saved(user, [failed], status=SourceStatus.FAILED, age=TWO_DAYS)
        scenario.check(
            "pending and processing both show as processing",
            ["failed"] + ["processing"] * 5,
            sorted(status for _, status in user.listed()),
        )

        reel = loop.reel()
        scenario.check("new save", (429, "quota_exceeded"), _error(user.save(reel.url)))
        scenario.check("nothing stored for the refused Reel", 0, loop.source_count(reel))
        scenario.check(
            "retrying the failed Reel", (429, "quota_exceeded"), _error(user.save(failed.url))
        )
        scenario.check(
            "the refused retry leaves the Reel failed and unqueued",
            ("failed", 0),
            (loop.source(failed)["status"], loop.messages_queued(failed)),
        )
        resave = user.save(processing[0].url)
        scenario.check(
            "re-saving a Reel that is still processing",
            (202, "processing"),
            (resave.status_code, resave.json().get("status")),
        )
        other = loop.user()
        scenario.check("another user saves the Reel", 202, other.save(reel.url).status_code)


def test_retries_count_toward_the_rate_limit(report, loop) -> None:
    with report.scenario(
        "Users keep retrying Reels that keep failing",
        ["Q5"],
        "Instagram refuses every download. User one retries two failed Reels from two days "
        "ago, alternating; user two saves two new Reels and then retries them",
    ) as scenario:
        user = loop.user()
        old = [loop.reel(download_error=INSTAGRAM_REFUSED) for _ in range(2)]
        loop.seed_saved(user, old, status=SourceStatus.FAILED, age=TWO_DAYS)
        outcomes = []
        for reel in (old[0], old[1], old[0]):
            retry = user.save(reel.url)
            outcomes.append((retry.status_code, retry.json().get("status")))
            loop.run_worker()
        scenario.check(
            "three retries across two Reels within the minute",
            [(202, "processing")] * 3,
            outcomes,
        )
        scenario.check("fourth retry", (429, "rate_limited"), _error(user.save(old[1].url)))
        scenario.check(
            "the refused retry leaves the Reel failed and unqueued",
            ("failed", 0, 1),
            (
                loop.source(old[1])["status"],
                loop.messages_queued(old[1]),
                loop.messages_sent(old[1]),
            ),
        )

        other = loop.user()
        new = [loop.reel(download_error=INSTAGRAM_REFUSED) for _ in range(2)]
        scenario.check(
            "two new saves", [202, 202], [other.save(reel.url).status_code for reel in new]
        )
        loop.run_worker()
        retry = other.save(new[0].url)
        scenario.check(
            "retry after two new saves",
            (202, "processing"),
            (retry.status_code, retry.json().get("status")),
        )
        loop.run_worker()
        scenario.check(
            "retry after two new saves and one retry",
            (429, "rate_limited"),
            _error(other.save(new[1].url)),
        )


# Extract


def test_book_enrichment_outcomes(report, loop) -> None:
    with report.scenario(
        "Books confirms one book, cannot confirm another, and is down for a third",
        ["X1", "X2", "X3", "X8"],
        "Reel one mentions three books: one Books confirms, one Books only has a summary "
        "edition of, one Books answers with a 500; Reel two mentions the confirmed book again",
    ) as scenario:
        confirmed = _volume("Tomorrow, and Tomorrow, and Tomorrow", ["Gabrielle Zevin"])
        summary = _volume("Summary of The Nightingale", ["Quick Reads"], subtitle="A Novel")
        queries = {
            "confirmed": _books_query("Tomorrow, and Tomorrow, and Tomorrow", "Gabrielle Zevin"),
            "summary only": _books_query("The Nightingale", "Kristin Hannah"),
            "outage": _books_query("Dune", "Frank Herbert"),
        }
        loop.books.volumes(queries["confirmed"], [confirmed])
        loop.books.volumes(queries["summary only"], [summary])
        loop.books.outage(queries["outage"])
        confirmed_mention = {
            "title": "Tomorrow, and Tomorrow, and Tomorrow",
            "author": "Gabrielle Zevin",
            "category": "book",
            "confidence": 0.8,
        }
        first = loop.reel(
            [
                confirmed_mention,
                {
                    "title": "The Nightingale",
                    "author": "Kristin Hannah",
                    "category": "book",
                    "confidence": 0.85,
                },
                {"title": "Dune", "author": "Frank Herbert", "category": "book", "confidence": 0.6},
            ]
        )
        second = loop.reel([confirmed_mention])
        user = loop.user()
        first_id = user.save(first.url).json()["id"]
        second_id = user.save(second.url).json()["id"]
        loop.run_worker()

        first_saved = user.saved(first_id)
        second_saved = user.saved(second_id)
        scenario.check(
            "both Reels done", ["done", "done"], [first_saved["status"], second_saved["status"]]
        )
        fields = ("title", "author", "book_id", "google_books_url", "cover_image_url", "confidence")
        book_id = loop.book_rows(confirmed)
        scenario.check("catalog rows for the confirmed book", 1, len(book_id))
        scenario.check(
            "items of Reel one",
            [
                {
                    "title": confirmed_mention["title"],
                    "author": confirmed_mention["author"],
                    "book_id": book_id[0],
                    "google_books_url": confirmed["volumeInfo"]["infoLink"],
                    "cover_image_url": confirmed["volumeInfo"]["imageLinks"]["thumbnail"].replace(
                        "http://", "https://", 1
                    ),
                    "confidence": 0.85,
                },
                {
                    "title": "The Nightingale",
                    "author": "Kristin Hannah",
                    "book_id": None,
                    "google_books_url": None,
                    "cover_image_url": None,
                    "confidence": 0.85,
                },
                {
                    "title": "Dune",
                    "author": "Frank Herbert",
                    "book_id": None,
                    "google_books_url": None,
                    "cover_image_url": None,
                    "confidence": 0.6,
                },
            ],
            [_item_view(item, *fields) for item in first_saved["items"]],
        )
        scenario.check("the summary edition is not stored", [], loop.book_rows(summary))
        scenario.check(
            "Reel two points at the same catalog row",
            [book_id[0]],
            [item["book_id"] for item in second_saved["items"]],
        )
        scenario.check(
            "Books queries in order",
            [
                queries["confirmed"],
                queries["summary only"],
                queries["outage"],
                queries["confirmed"],
            ],
            [request["q"] for request in loop.books_requests()],
        )


def test_irrelevant_reel_skips_the_extraction(report, loop) -> None:
    with report.scenario(
        "The relevance gate finds nothing worth extracting",
        ["X6", "V1"],
        "The gate answers irrelevant; the extraction reply would have a product",
    ) as scenario:
        reel = loop.reel(
            [{"title": "Should Not Appear", "category": "product", "confidence": 0.9}],
            gate=gemini_gate_reply("irrelevant", "a dance clip with no picks"),
        )
        user = loop.user()
        saved_id = user.save(reel.url).json()["id"]
        loop.run_worker()

        saved = user.saved(saved_id)
        scenario.check(
            "saved source",
            {"status": "done", "skip_reason": "a dance clip with no picks", "error_message": None},
            {key: saved[key] for key in ("status", "skip_reason", "error_message")},
        )
        scenario.check("items", [], saved["items"])
        scenario.check(
            "Gemini calls for this Reel", [GATE], loop.gemini.models_called_for(reel.shortcode)
        )


def test_failed_download_is_retried_by_saving_again(report, loop) -> None:
    with report.scenario(
        "Instagram refuses the download, then the user retries by saving again",
        ["X7", "C3", "V1"],
        "Two users save the Reel; yt-dlp fails like an Instagram login wall; then Instagram "
        "recovers and the first user saves the Reel again",
    ) as scenario:
        reel = loop.reel(
            [{"title": "Moleskine Classic Notebook", "category": "product", "confidence": 0.9}],
            download_error=INSTAGRAM_REFUSED,
        )
        first, second = loop.user(), loop.user()
        first_id = first.save(reel.url).json()["id"]
        second_id = second.save(reel.url).json()["id"]
        loop.run_worker()

        failed = first.saved(first_id)
        scenario.check(
            "after the failed download",
            {"status": "failed", "error_message": DOWNLOAD_FAILED, "items": []},
            {key: failed[key] for key in ("status", "error_message", "items")},
        )
        scenario.check(
            "the other user sees the failure", "failed", second.saved(second_id)["status"]
        )
        scenario.check("Gemini never called", [], loop.gemini.models_called_for(reel.shortcode))

        loop.yt_dlp.set_error(reel.shortcode, None)
        retry = first.save(reel.url)
        scenario.check(
            "retry response",
            (202, first_id, "processing", None),
            (
                retry.status_code,
                retry.json()["id"],
                retry.json()["status"],
                retry.json()["error_message"],
            ),
        )
        scenario.check(
            "the other user sees the retry", "processing", second.saved(second_id)["status"]
        )
        scenario.check("messages queued for the retry", 1, loop.messages_queued(reel))
        loop.run_worker()

        scenario.check(
            "both users after the retry",
            [("done", ["Moleskine Classic Notebook"])] * 2,
            [
                (saved["status"], [item["title"] for item in saved["items"]])
                for saved in (first.saved(first_id), second.saved(second_id))
            ],
        )


REFUSED_TITLE = "Refused by the database"


@contextmanager
def _database_refuses_title(loop: Loop, title: str) -> Iterator[None]:
    """Make the suite's own database refuse one item title, like any failed write would."""
    literal = title.replace("'", "''")
    with loop.admin_engine.begin() as connection:
        connection.execute(
            text(
                f"""
                create function e2e_refuse_item() returns trigger language plpgsql as $$
                begin
                  if new.title = '{literal}' then
                    raise exception 'e2e: database refused %', new.title;
                  end if;
                  return new;
                end $$;
                create trigger e2e_refuse_item before insert on source_items
                  for each row execute function e2e_refuse_item();
                """
            )
        )
    try:
        yield
    finally:
        with loop.admin_engine.begin() as connection:
            connection.execute(text("drop trigger e2e_refuse_item on source_items"))
            connection.execute(text("drop function e2e_refuse_item()"))


def test_database_refusing_the_items_fails_the_reel(report, loop) -> None:
    with report.scenario(
        "The database refuses the extracted items",
        ["X9"],
        "A trigger in the suite's database refuses one of the two extracted items, so "
        "storing the extraction fails after Gemini answered",
    ) as scenario:
        reel = loop.reel(
            [
                {"title": "Pilot Kakuno", "category": "product", "confidence": 0.9},
                {"title": REFUSED_TITLE, "category": "product", "confidence": 0.8},
            ]
        )
        user = loop.user()
        saved_id = user.save(reel.url).json()["id"]
        with _database_refuses_title(loop, REFUSED_TITLE):
            try:
                loop.run_worker()
                worker_error = None
            except Exception as exc:
                worker_error = f"{type(exc).__name__}: {exc}"
        scenario.check("worker run finishes", None, worker_error)
        saved = user.saved(saved_id)
        scenario.check(
            "the Reel is failed with nothing half-stored",
            {"status": "failed", "error_message": UNEXPECTED_ERROR, "items": []},
            {key: saved[key] for key in ("status", "error_message", "items")},
        )
        scenario.check("stored items", 0, loop.item_count(reel))
        scenario.check("queue message archived", 0, loop.messages_queued(reel))


# Shared cache


def test_second_user_gets_the_cached_result(report, loop) -> None:
    with report.scenario(
        "A second user saves a Reel another user already extracted",
        ["C1"],
        "User one saves and the worker extracts the Reel; then user two saves it",
    ) as scenario:
        query = _books_query("Piranesi", "Susanna Clarke")
        loop.books.volumes(query, [_volume("Piranesi", ["Susanna Clarke"])])
        reel = loop.reel(
            [
                {
                    "title": "Piranesi",
                    "author": "Susanna Clarke",
                    "category": "book",
                    "confidence": 0.9,
                },
                {"title": "Kobo Libra", "category": "product", "confidence": 0.7},
            ]
        )
        first, second = loop.user(), loop.user()
        first_id = first.save(reel.url).json()["id"]
        loop.run_worker()
        provider_calls = (
            len(loop.gemini.models_called_for(reel.shortcode)),
            len(loop.books_requests()),
            len(loop.yt_dlp.calls(reel.shortcode)),
        )

        response = second.save(reel.url)
        cached = response.json()
        original = first.saved(first_id)
        scenario.check("second save", (202, "done"), (response.status_code, cached["status"]))
        scenario.check("a save of their own", True, cached["id"] != first_id)
        scenario.check("same items as the first user", original["items"], cached["items"])
        scenario.check("extraction messages sent", 1, loop.messages_sent(reel))
        resave = first.save(reel.url)
        scenario.check(
            "user one saving again gets their own save",
            (202, first_id),
            (resave.status_code, resave.json().get("id")),
        )
        scenario.check(
            "no new Gemini, Books, or yt-dlp calls",
            provider_calls,
            (
                len(loop.gemini.models_called_for(reel.shortcode)),
                len(loop.books_requests()),
                len(loop.yt_dlp.calls(reel.shortcode)),
            ),
        )


def test_users_saving_a_pending_reel_share_one_extraction(report, loop) -> None:
    with report.scenario(
        "Two users save a Reel before it is extracted",
        ["C2"],
        "Both users save the Reel, then the worker runs",
    ) as scenario:
        reel = loop.reel([{"title": "Aesop Hand Balm", "category": "product", "confidence": 0.8}])
        first, second = loop.user(), loop.user()
        saves = [first.save(reel.url).json(), second.save(reel.url).json()]
        scenario.check(
            "both saves while pending", ["processing", "processing"], [s["status"] for s in saves]
        )
        scenario.check("extraction messages sent", 1, loop.messages_sent(reel))
        loop.run_worker()

        scenario.check(
            "both users after one run",
            [("done", ["Aesop Hand Balm"])] * 2,
            [
                (saved["status"], [item["title"] for item in saved["items"]])
                for saved in (first.saved(saves[0]["id"]), second.saved(saves[1]["id"]))
            ],
        )
        scenario.check(
            "Gemini extraction calls",
            1,
            loop.gemini.models_called_for(reel.shortcode).count(EXTRACTION),
        )


def test_first_save_of_a_reel_that_failed_for_someone_else_retries_it(report, loop) -> None:
    with report.scenario(
        "A user saves a Reel that already failed for another user",
        ["C4"],
        "User one's save fails because Instagram refused the download; Instagram recovers; "
        "user two saves the Reel for the first time",
    ) as scenario:
        reel = loop.reel(
            [{"title": "Lamy Safari", "category": "product", "confidence": 0.9}],
            download_error=INSTAGRAM_REFUSED,
        )
        first, second = loop.user(), loop.user()
        first.save(reel.url)
        loop.run_worker()
        scenario.check("the Reel failed for user one", "failed", loop.source(reel)["status"])
        loop.yt_dlp.set_error(reel.shortcode, None)

        response = second.save(reel.url)
        scenario.check("user two's save status", 202, response.status_code)
        scenario.check(
            "user two's save starts a new attempt",
            ("processing", 2),
            (response.json()["status"], loop.messages_sent(reel)),
        )


def test_resaving_a_deleted_failed_reel_retries_it(report, loop) -> None:
    with report.scenario(
        "A user deletes a failed save and saves the Reel again",
        ["C4"],
        "The only saver's download fails; they delete the save; Instagram recovers; they "
        "save the Reel again",
    ) as scenario:
        reel = loop.reel(
            [{"title": "Kaweco Sport", "category": "product", "confidence": 0.9}],
            download_error=INSTAGRAM_REFUSED,
        )
        user = loop.user()
        first_id = user.save(reel.url).json()["id"]
        loop.run_worker()
        scenario.check("the first save failed", "failed", user.saved(first_id)["status"])
        scenario.check("delete status", 200, user.delete(first_id).status_code)
        loop.yt_dlp.set_error(reel.shortcode, None)

        again = user.save(reel.url)
        scenario.check(
            "the new save starts a new attempt",
            (202, "processing", 2),
            (again.status_code, again.json()["status"], loop.messages_sent(reel)),
        )
        loop.run_worker()
        scenario.check(
            "the retry is extracted",
            ("done", ["Kaweco Sport"]),
            (
                user.saved(again.json()["id"])["status"],
                [item["title"] for item in user.saved(again.json()["id"])["items"]],
            ),
        )


# Revisit


def test_list_is_newest_first_and_limited(report, loop) -> None:
    with report.scenario(
        "A user revisits their saved Reels",
        ["V2"],
        "One user saves three Reels in order; the list is read with several limits",
    ) as scenario:
        user = loop.user()
        ids = [user.save(loop.reel().url).json()["id"] for _ in range(3)]
        loop.run_worker()
        newest_first = list(reversed(ids))
        scenario.check("default list", newest_first, [s["id"] for s in user.list().json()])
        scenario.check("limit=2", newest_first[:2], [s["id"] for s in user.list(limit=2).json()])
        scenario.check("limit=100", newest_first, [s["id"] for s in user.list(limit=100).json()])
        scenario.check(
            "out-of-range limits",
            {0: (422, "validation_error"), 101: (422, "validation_error")},
            {limit: _error(user.list(limit=limit)) for limit in (0, 101)},
        )


def test_users_never_see_each_others_saves(report, loop, database) -> None:
    with report.scenario(
        "Two users with their own saves",
        ["V3"],
        "User one saves a Reel; user two saves another; each reads, and user two tries to read "
        "and delete user one's save; then RLS is checked directly as the API role",
    ) as scenario:
        first, second = loop.user(), loop.user()
        first_id = first.save(loop.reel().url).json()["id"]
        second_id = second.save(loop.reel().url).json()["id"]
        loop.run_worker()

        scenario.check("user one's list", [first_id], [s["id"] for s in first.list().json()])
        scenario.check("user two's list", [second_id], [s["id"] for s in second.list().json()])
        scenario.check(
            "user two reads user one's save",
            (404, "saved_source_not_found"),
            _error(second.get(first_id)),
        )
        scenario.check(
            "user two deletes user one's save",
            (404, "saved_source_not_found"),
            _error(second.delete(first_id)),
        )
        scenario.check("user one's save is still there", 200, first.get(first_id).status_code)
        scenario.check(
            "malformed and unknown ids",
            [(404, "saved_source_not_found")] * 2,
            [_error(second.get("not-a-uuid")), _error(second.get(str(uuid4())))],
        )

        api_role = create_sql_engine(database.api_url)
        try:
            with api_role.connect() as connection:
                unscoped = connection.execute(text("select count(*) from saved_sources")).scalar()
                connection.execute(
                    text("select set_config('app.current_user_id', :owner, true)"),
                    {"owner": second.id},
                )
                owners = (
                    connection.execute(text("select distinct owner_id::text from saved_sources"))
                    .scalars()
                    .all()
                )
                try:
                    connection.execute(
                        text(
                            "insert into saved_sources (owner_id, source_id) select "
                            "cast(:owner as uuid), source_id from saved_sources limit 1"
                        ),
                        {"owner": first.id},
                    )
                    insert_refused = False
                except ProgrammingError as exc:
                    insert_refused = "row-level security" in str(exc)
                connection.rollback()
        finally:
            api_role.dispose()
        scenario.check("API role without a user sees no saves", 0, unscoped)
        scenario.check("API role as user two sees only user two's saves", [second.id], owners)
        scenario.check("API role as user two cannot save for user one", True, insert_refused)


def test_deleting_a_save_leaves_other_users_untouched(report, loop) -> None:
    with report.scenario(
        "A user deletes a Reel another user also saved, then saves it again",
        ["V4"],
        "Two users save the Reel and it is extracted; user one deletes it, deletes again, and "
        "later saves it again",
    ) as scenario:
        reel = loop.reel([{"title": "Leuchtturm1917", "category": "product", "confidence": 0.9}])
        first, second = loop.user(), loop.user()
        first_id = first.save(reel.url).json()["id"]
        second_id = second.save(reel.url).json()["id"]
        loop.run_worker()
        gemini_calls = len(loop.gemini.models_called_for(reel.shortcode))

        deleted = first.delete(first_id)
        scenario.check(
            "delete response",
            (200, {"id": first_id, "deleted": True}),
            (deleted.status_code, deleted.json()),
        )
        scenario.check("user one's list", [], first.listed())
        scenario.check("user one reads the deleted save", 404, first.get(first_id).status_code)
        scenario.check(
            "user one deletes it again",
            (404, "saved_source_not_found"),
            _error(first.delete(first_id)),
        )
        other = second.saved(second_id)
        scenario.check(
            "user two's save",
            ("done", ["Leuchtturm1917"]),
            (other["status"], [i["title"] for i in other["items"]]),
        )
        scenario.check(
            "shared source and items kept",
            ("done", 1),
            (loop.source(reel)["status"], loop.item_count(reel)),
        )

        resave = first.save(reel.url)
        scenario.check(
            "saving it again",
            (202, "done", ["Leuchtturm1917"]),
            (
                resave.status_code,
                resave.json()["status"],
                [i["title"] for i in resave.json()["items"]],
            ),
        )
        scenario.check("a new save id", True, resave.json()["id"] != first_id)
        scenario.check("extraction messages sent", 1, loop.messages_sent(reel))
        scenario.check(
            "no new Gemini calls", gemini_calls, len(loop.gemini.models_called_for(reel.shortcode))
        )


def test_deleting_a_save_while_it_is_processing(report, loop) -> None:
    with report.scenario(
        "A user deletes a Reel before it is extracted",
        ["V5"],
        "The user saves a Reel and deletes it before the worker runs; then saves it again",
    ) as scenario:
        reel = loop.reel([{"title": "Baggu Tote", "category": "product", "confidence": 0.8}])
        user = loop.user()
        saved_id = user.save(reel.url).json()["id"]
        scenario.check("delete while processing", 200, user.delete(saved_id).status_code)
        loop.run_worker()

        scenario.check("the Reel is still extracted once", "done", loop.source(reel)["status"])
        scenario.check("user's list after the worker ran", [], user.listed())
        resave = user.save(reel.url)
        scenario.check(
            "saving it again",
            (202, "done", ["Baggu Tote"]),
            (
                resave.status_code,
                resave.json()["status"],
                [i["title"] for i in resave.json()["items"]],
            ),
        )
        scenario.check("extraction messages sent", 1, loop.messages_sent(reel))
