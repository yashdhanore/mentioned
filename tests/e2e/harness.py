"""Shared plumbing for E2E suites that run against the local stack from `make dev`.

A suite records every check into a `Report`, which writes
`outputs/e2e/<suite>/<run>/report.json` (plus the logs of any API process it booted) and a
copy at `outputs/e2e/<suite>/latest.json`, so each run leaves a reviewable artifact.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUTS_DIR = REPO_ROOT / "outputs" / "e2e"
# The same least-privilege roles and passwords `scripts/dev-up.sh` creates.
API_DATABASE_URL = "postgresql://mentioned_api:local-dev-api-pw@127.0.0.1:54322/postgres"
WORKER_DATABASE_URL = "postgresql://mentioned_worker:local-dev-worker-pw@127.0.0.1:54322/postgres"
API_BOOT_TIMEOUT_SECONDS = 30


def _local_stack() -> dict[str, str] | None:
    try:
        result = subprocess.run(
            ["supabase", "status", "-o", "env"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    values = {}
    for line in result.stdout.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            values[key.strip()] = value.strip().strip('"')
    required = {"API_URL", "ANON_KEY", "SERVICE_ROLE_KEY", "DB_URL"}
    return values if required <= values.keys() else None


STACK = _local_stack()
# CI sets E2E_REQUIRED so a broken stack setup fails the job instead of skipping to green.
if STACK is None and os.getenv("E2E_REQUIRED"):
    raise RuntimeError("E2E_REQUIRED is set but `supabase status` found no local stack")
requires_local_stack = pytest.mark.skipif(
    STACK is None, reason="needs the local Supabase stack; start it with `make dev`"
)


def admin_database_url() -> str:
    """The local superuser URL, for seeding and inspecting rows around RLS."""
    assert STACK is not None
    return STACK["DB_URL"].replace("postgresql://", "postgresql+psycopg://", 1)


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)
    return result.stdout.strip()


class Report:
    """Collects every check so the run leaves a reviewable artifact behind."""

    def __init__(self, suite: str, rerun: str) -> None:
        self.suite = suite
        self.rerun = rerun
        self.started_at = datetime.now(UTC)
        self.suite_dir = OUTPUTS_DIR / suite
        # One folder per run holds the report and every API process log from that run.
        self.run_dir = self.suite_dir / self.started_at.strftime("%Y%m%dT%H%M%SZ")
        self.scenarios: list[dict[str, Any]] = []
        # Suite-level facts a reviewer needs to trust the run, such as which fakes stood in
        # for which providers.
        self.context: dict[str, Any] = {}

    def scenario(
        self, name: str, failure_modes: list[str], setup: str, known_bug: str | None = None
    ) -> Scenario:
        scenario = Scenario(name, failure_modes, setup, known_bug)
        self.scenarios.append(scenario.record)
        return scenario

    def write(self) -> Path:
        # A known bug that still fails keeps the run green, like a strict xfail; one that
        # starts passing turns it red so the marker gets removed.
        passed = bool(self.scenarios) and all(
            s["outcome"] in PASSING_OUTCOMES for s in self.scenarios
        )
        outcomes: dict[str, int] = {}
        for scenario in self.scenarios:
            outcomes[scenario["outcome"]] = outcomes.get(scenario["outcome"], 0) + 1
        payload = {
            "suite": self.suite,
            "started_at": self.started_at.isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
            "git_commit": _git("rev-parse", "HEAD"),
            "git_dirty": bool(_git("status", "--porcelain")),
            "supabase_api_url": STACK["API_URL"] if STACK else None,
            "rerun": self.rerun,
            "passed": passed,
            "outcomes": outcomes,
            "context": self.context,
            "scenarios": self.scenarios,
        }
        self.run_dir.mkdir(parents=True, exist_ok=True)
        path = self.run_dir / "report.json"
        text = json.dumps(payload, indent=2, default=str)
        path.write_text(text)
        (self.suite_dir / "latest.json").write_text(text)
        return path


KNOWN_BUG = "known bug"
PASSING_OUTCOMES = {"passed", KNOWN_BUG}


class Scenario:
    """Use as a context manager so a scenario that crashes is reported as an error, not a pass.

    `known_bug` marks a scenario that asserts the correct behavior of a product bug that is
    not fixed yet; pair it with `pytest.mark.xfail(strict=True)` on the test.
    """

    def __init__(
        self, name: str, failure_modes: list[str], setup: str, known_bug: str | None = None
    ) -> None:
        self.known_bug = known_bug
        self.record: dict[str, Any] = {
            "name": name,
            "failure_modes": failure_modes,
            "setup": setup,
            "outcome": "not finished",
            "checks": [],
        }
        if known_bug:
            self.record["known_bug"] = known_bug

    def __enter__(self) -> Scenario:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, _tb
    ) -> bool:
        if exc is None:
            if not self.record["checks"]:
                self.record["outcome"] = "no checks"
            elif self.known_bug:
                self.record["outcome"] = "passed unexpectedly"
            else:
                self.record["outcome"] = "passed"
        elif isinstance(exc, AssertionError):
            self.record["outcome"] = KNOWN_BUG if self.known_bug else "failed"
        else:
            self.record["outcome"] = "error"
            self.record["error"] = f"{exc_type.__name__}: {exc}" if exc_type else str(exc)
        return False

    def check(self, label: str, expected: Any, actual: Any) -> None:
        passed = expected == actual
        self.record["checks"].append(
            {"check": label, "expected": expected, "actual": actual, "passed": passed}
        )
        assert passed, f"{label}: expected {expected!r}, got {actual!r}"


class IsolatedDatabase:
    """A database of its own in the local Postgres, migrated by Alembic like production.

    The `make dev` worker polls the `extract_sources` queue in the `postgres` database, and
    the API queues every new save with no delay, so a Reel saved through the API there would
    be taken by that worker, which then downloads it from Instagram. A suite that saves
    through the API uses this database instead, where only the suite's own worker runs.
    Roles are cluster-wide, so the API and worker still connect as `mentioned_api` and
    `mentioned_worker` under the same grants and RLS policies as `make dev` and production.
    """

    NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")

    def __init__(self, name: str) -> None:
        assert STACK is not None
        if not self.NAME_RE.match(name):
            raise ValueError(f"not a safe database name: {name!r}")
        self.name = name
        self.admin_url = self._with_database(STACK["DB_URL"])
        self.api_url = self._with_database(API_DATABASE_URL)
        self.worker_url = self._with_database(WORKER_DATABASE_URL)

    def _with_database(self, url: str) -> str:
        return make_url(url).set(database=self.name).render_as_string(hide_password=False)

    def _maintenance(self, statement: str) -> None:
        engine = create_engine(admin_database_url(), isolation_level="AUTOCOMMIT")
        try:
            with engine.connect() as connection:
                connection.execute(text(statement))
        finally:
            engine.dispose()

    def create(self) -> None:
        # A run that was killed leaves its database behind; start from a clean one.
        self.drop()
        self._maintenance(f'create database "{self.name}"')
        env = dict(os.environ, DATABASE_URL=self.admin_url)
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"alembic upgrade failed:\n{result.stdout}\n{result.stderr}")

    def drop(self) -> None:
        self._maintenance(f'drop database if exists "{self.name}" with (force)')


def _is_this_machine(host: object) -> bool:
    if host is None:
        return True
    name = host.decode() if isinstance(host, bytes) else str(host)
    if name.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(name.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


class NetworkGuard:
    """Refuses every connection this process tries to open to another machine.

    E2E suites fake Instagram, Gemini, and Google Books; if code under test ever reached a
    real provider anyway (a missed base URL, a new provider), the call fails here and is
    recorded, instead of quietly contacting it. Subprocesses are not covered.
    """

    def __init__(self) -> None:
        self.blocked: list[str] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        real_getaddrinfo = socket.getaddrinfo
        real_connect = socket.socket.connect
        guard = self

        def getaddrinfo(host, *args, **kwargs):
            if not _is_this_machine(host):
                guard.blocked.append(f"resolve {host}")
                raise socket.gaierror(f"E2E network guard: refused to resolve {host}")
            return real_getaddrinfo(host, *args, **kwargs)

        def connect(sock, address):
            if sock.family in (socket.AF_INET, socket.AF_INET6) and not _is_this_machine(
                address[0]
            ):
                guard.blocked.append(f"connect {address[0]}")
                raise ConnectionRefusedError(f"E2E network guard: refused {address[0]}")
            return real_connect(sock, address)

        monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
        monkeypatch.setattr(socket.socket, "connect", connect)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def api_env(**overrides: str) -> dict[str, str]:
    """A fully pinned API environment, so the developer's `.env` cannot change the result.

    `get_settings()` loads `.env` without overriding variables that are already set, and an
    empty string counts as set, which is how a scenario removes a value.
    """
    assert STACK is not None
    env = dict(os.environ)
    env.update(
        {
            "APP_ENV": "development",
            "AUTH_MODE": "supabase",
            "DATABASE_URL": API_DATABASE_URL,
            "WORKER_DATABASE_URL": "",
            "AUTO_CREATE_TABLES": "false",
            "SUPABASE_PROJECT_URL": STACK["API_URL"],
            "SUPABASE_SERVICE_ROLE_KEY": STACK["SERVICE_ROLE_KEY"],
            "SUPABASE_JWT_SECRET": "",
            "SUPABASE_JWT_AUDIENCE": "authenticated",
            "WEB_BASE_URL": "",
        }
    )
    env.update(overrides)
    return env


def start_api(
    report: Report, env: dict[str, str], host: str | None = None
) -> tuple[subprocess.Popen[str], str]:
    """Boot the API as its own process; `host` is the Host header production trusts."""
    port = free_port()
    report.run_dir.mkdir(parents=True, exist_ok=True)
    log_path = report.run_dir / f"api-{port}.log"
    with log_path.open("w") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "src.main:app", "--port", str(port)],
            cwd=REPO_ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
    base_url = f"http://127.0.0.1:{port}"
    headers = {"Host": host} if host else {}
    deadline = time.monotonic() + API_BOOT_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"API exited during boot:\n{log_path.read_text()}")
        try:
            if httpx.get(f"{base_url}/health", headers=headers, timeout=1).status_code == 200:
                return process, base_url
        except httpx.TransportError:
            pass
        time.sleep(0.2)
    process.kill()
    raise RuntimeError(f"API did not become healthy in time:\n{log_path.read_text()}")


def stop_api(process: subprocess.Popen[str]) -> None:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
