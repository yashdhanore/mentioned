"""End-to-end account deletion against the real local stack (`make dev`).

Each scenario boots its own API process with a specific configuration, signs in as a real
Supabase Auth user, calls `DELETE /v1/account`, and then checks the outcome the way a user
would experience it: can the login still sign in or refresh, and is the data still there.

Every check is recorded, pass or fail, into a JSON report under
`outputs/e2e/account-deletion/` so a run can be inspected and compared later.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from sqlmodel import Session, create_engine, func, select

from src.push.models import PushToken
from src.sources.models import SavedSource, Source, SourceStatus

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "outputs" / "e2e" / "account-deletion"
# One folder per run holds the report and every API process log from that run.
RUN_STARTED_AT = datetime.now(UTC)
RUN_DIR = REPORT_DIR / RUN_STARTED_AT.strftime("%Y%m%dT%H%M%SZ")
RERUN_COMMAND = "make dev && uv run pytest tests/e2e/test_account_deletion.py -v"
# The same least-privilege API role and password `scripts/dev-up.sh` creates.
API_DATABASE_URL = "postgresql://mentioned_api:local-dev-api-pw@127.0.0.1:54322/postgres"
PASSWORD = "e2e-account-deletion-pw"
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
pytestmark = pytest.mark.skipif(
    STACK is None, reason="needs the local Supabase stack; start it with `make dev`"
)


class Report:
    """Collects every check so the run leaves a reviewable artifact behind."""

    def __init__(self) -> None:
        self.scenarios: list[dict[str, Any]] = []

    def scenario(self, name: str, failure_modes: list[str], setup: str) -> Scenario:
        scenario = Scenario(name, failure_modes, setup)
        self.scenarios.append(scenario.record)
        return scenario

    def write(self) -> Path:
        passed = bool(self.scenarios) and all(s["outcome"] == "passed" for s in self.scenarios)
        payload = {
            "suite": "account-deletion",
            "started_at": RUN_STARTED_AT.isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
            "git_commit": _git("rev-parse", "HEAD"),
            "git_dirty": bool(_git("status", "--porcelain")),
            "supabase_api_url": STACK["API_URL"] if STACK else None,
            "rerun": RERUN_COMMAND,
            "passed": passed,
            "scenarios": self.scenarios,
        }
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        path = RUN_DIR / "report.json"
        text = json.dumps(payload, indent=2, default=str)
        path.write_text(text)
        (REPORT_DIR / "latest.json").write_text(text)
        return path


class Scenario:
    """Use as a context manager so a scenario that crashes is reported as an error, not a pass."""

    def __init__(self, name: str, failure_modes: list[str], setup: str) -> None:
        self.record: dict[str, Any] = {
            "name": name,
            "failure_modes": failure_modes,
            "setup": setup,
            "outcome": "not finished",
            "checks": [],
        }

    def __enter__(self) -> Scenario:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, _tb
    ) -> bool:
        if exc is None:
            self.record["outcome"] = "passed" if self.record["checks"] else "no checks"
        elif isinstance(exc, AssertionError):
            self.record["outcome"] = "failed"
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


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)
    return result.stdout.strip()


@pytest.fixture(scope="module")
def report():
    report = Report()
    yield report
    path = report.write()
    print(f"\naccount deletion E2E report: {path}")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _api_env(**overrides: str) -> dict[str, str]:
    """A fully pinned API environment, so the developer's `.env` cannot change the result.

    `get_settings()` loads `.env` without overriding variables that are already set, and an
    empty string counts as set, which is how a scenario removes the service-role key.
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


def _start_api(env: dict[str, str], host: str | None = None) -> tuple[subprocess.Popen[str], str]:
    """Boot the API as its own process; `host` is the Host header production trusts."""
    port = _free_port()
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    log_path = RUN_DIR / f"api-{port}.log"
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


def _stop_api(process: subprocess.Popen[str]) -> None:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


@pytest.fixture(scope="module")
def api_factory():
    processes: list[subprocess.Popen[str]] = []

    def start(**overrides: str) -> str:
        process, base_url = _start_api(_api_env(**overrides))
        processes.append(process)
        return base_url

    yield start
    for process in processes:
        _stop_api(process)


class AuthUsers:
    """Real Supabase Auth users on the local stack, cleaned up after the module."""

    def __init__(self) -> None:
        assert STACK is not None
        self.auth_url = STACK["API_URL"].rstrip("/") + "/auth/v1"
        self.admin_headers = {
            "apikey": STACK["SERVICE_ROLE_KEY"],
            "Authorization": f"Bearer {STACK['SERVICE_ROLE_KEY']}",
        }
        self.anon_headers = {"apikey": STACK["ANON_KEY"]}
        self.created: list[str] = []

    def create(self) -> tuple[str, str]:
        email = f"e2e-delete-{uuid4().hex[:10]}@example.com"
        response = httpx.post(
            f"{self.auth_url}/admin/users",
            headers=self.admin_headers,
            json={"email": email, "password": PASSWORD, "email_confirm": True},
        )
        response.raise_for_status()
        user_id = response.json()["id"]
        self.created.append(user_id)
        return user_id, email

    def sign_in(self, email: str) -> httpx.Response:
        return httpx.post(
            f"{self.auth_url}/token?grant_type=password",
            headers=self.anon_headers,
            json={"email": email, "password": PASSWORD},
        )

    def refresh(self, refresh_token: str) -> httpx.Response:
        return httpx.post(
            f"{self.auth_url}/token?grant_type=refresh_token",
            headers=self.anon_headers,
            json={"refresh_token": refresh_token},
        )

    def session(self, email: str) -> dict[str, Any]:
        response = self.sign_in(email)
        response.raise_for_status()
        return response.json()

    def cleanup(self) -> None:
        for user_id in self.created:
            httpx.delete(f"{self.auth_url}/admin/users/{user_id}", headers=self.admin_headers)


@pytest.fixture(scope="module")
def auth_users():
    users = AuthUsers()
    yield users
    users.cleanup()


class OwnedData:
    """Seeds and counts a user's rows through an admin connection that bypasses RLS."""

    def __init__(self) -> None:
        assert STACK is not None
        url = STACK["DB_URL"].replace("postgresql://", "postgresql+psycopg://", 1)
        self.engine = create_engine(url)
        self.owners: list[UUID] = []
        self.sources: list[UUID] = []

    def seed(self, owner_id: str) -> None:
        # A saved source is inserted directly: creating one through the API would queue a
        # real extraction for the running `make dev` worker to pick up.
        owner_uuid = UUID(owner_id)
        external_id = f"E2EDEL{uuid4().hex[:12]}"
        with Session(self.engine) as session:
            source = Source(
                source_key=f"instagram:reel:{external_id}",
                platform="instagram",
                source_type="reel",
                external_id=external_id,
                canonical_url=f"https://www.instagram.com/reel/{external_id}/",
                status=SourceStatus.DONE,
            )
            session.add(source)
            session.flush()
            session.add(SavedSource(owner_id=owner_uuid, source_id=source.id))
            session.add(
                PushToken(
                    owner_id=owner_uuid,
                    expo_push_token=f"ExponentPushToken[{external_id}]",
                    platform="ios",
                )
            )
            session.commit()
            self.sources.append(source.id)
        self.owners.append(owner_uuid)

    def counts(self, owner_id: str) -> dict[str, int]:
        owner_uuid = UUID(owner_id)
        with Session(self.engine) as session:
            saved = session.exec(
                select(func.count()).where(SavedSource.owner_id == owner_uuid)
            ).one()
            tokens = session.exec(
                select(func.count()).where(PushToken.owner_id == owner_uuid)
            ).one()
        return {"saved_sources": saved, "push_tokens": tokens}

    def cleanup(self) -> None:
        with Session(self.engine) as session:
            for owner_uuid in self.owners:
                for model in (SavedSource, PushToken):
                    for row in session.exec(select(model).where(model.owner_id == owner_uuid)):
                        session.delete(row)
            session.flush()
            for source_id in self.sources:
                source = session.get(Source, source_id)
                if source is not None:
                    session.delete(source)
            session.commit()
        self.engine.dispose()


@pytest.fixture(scope="module")
def owned_data():
    data = OwnedData()
    yield data
    data.cleanup()


SEEDED = {"saved_sources": 1, "push_tokens": 1}
DELETED = {"saved_sources": 0, "push_tokens": 0}


def _delete_account(base_url: str, bearer: str) -> httpx.Response:
    return httpx.delete(
        f"{base_url}/v1/account", headers={"Authorization": f"Bearer {bearer}"}, timeout=30
    )


def test_user_deletes_account_and_can_no_longer_sign_in(
    report, api_factory, auth_users, owned_data
) -> None:
    with report.scenario(
        "Signed-in user deletes their account (production configuration)",
        ["F1", "F5", "F7", "F8"],
        "AUTH_MODE=supabase with the service-role key; a second user must be untouched",
    ) as scenario:
        api = api_factory()
        user_id, email = auth_users.create()
        other_id, other_email = auth_users.create()
        owned_data.seed(user_id)
        owned_data.seed(other_id)
        session = auth_users.session(email)

        response = _delete_account(api, session["access_token"])
        scenario.check("DELETE /v1/account status", 200, response.status_code)
        scenario.check("DELETE /v1/account body", {"deleted": True}, response.json())
        scenario.check("user's data after deletion", DELETED, owned_data.counts(user_id))
        sign_in = auth_users.sign_in(email)
        scenario.check("password sign-in after deletion", 400, sign_in.status_code)
        scenario.check(
            "sign-in error code", "invalid_credentials", sign_in.json().get("error_code")
        )
        refresh = auth_users.refresh(session["refresh_token"])
        scenario.check("refresh token after deletion is rejected", True, refresh.status_code >= 400)

        # The client may retry if it never saw the first response; its access token is still
        # valid until it expires, and the login is already gone.
        retry = _delete_account(api, session["access_token"])
        scenario.check("retried DELETE status", 200, retry.status_code)
        scenario.check("retried DELETE body", {"deleted": True}, retry.json())

        scenario.check("other user's data", SEEDED, owned_data.counts(other_id))
        scenario.check(
            "other user can still sign in", 200, auth_users.sign_in(other_email).status_code
        )


def test_missing_service_role_key_refuses_before_touching_data(
    report, api_factory, auth_users, owned_data
) -> None:
    with report.scenario(
        "API without the service-role key (the production bug)",
        ["F1", "F2"],
        "AUTH_MODE=supabase, APP_ENV=development, SUPABASE_SERVICE_ROLE_KEY empty",
    ) as scenario:
        api = api_factory(SUPABASE_SERVICE_ROLE_KEY="")
        user_id, email = auth_users.create()
        owned_data.seed(user_id)
        session = auth_users.session(email)

        response = _delete_account(api, session["access_token"])
        scenario.check("DELETE /v1/account status", 503, response.status_code)
        scenario.check("response does not claim deletion", False, "deleted" in response.json())
        scenario.check("user's data is untouched", SEEDED, owned_data.counts(user_id))
        scenario.check("login still signs in", 200, auth_users.sign_in(email).status_code)


def test_rejected_admin_call_reports_failure_and_keeps_login(
    report, api_factory, auth_users, owned_data
) -> None:
    with report.scenario(
        "Supabase admin API rejects the deletion",
        ["F6"],
        "AUTH_MODE=supabase with the anon key pasted in place of the service-role key",
    ) as scenario:
        api = api_factory(SUPABASE_SERVICE_ROLE_KEY=STACK["ANON_KEY"])
        user_id, email = auth_users.create()
        owned_data.seed(user_id)
        session = auth_users.session(email)

        response = _delete_account(api, session["access_token"])
        scenario.check("DELETE /v1/account status", 502, response.status_code)
        scenario.check("response does not claim deletion", False, "deleted" in response.json())
        # Data goes first on purpose, so the still-working login can retry the deletion.
        scenario.check("user's data is deleted", DELETED, owned_data.counts(user_id))
        scenario.check(
            "login still signs in so the user can retry", 200, auth_users.sign_in(email).status_code
        )


def test_dev_user_without_a_login_deletes_account_with_local_key(
    report, api_factory, owned_data
) -> None:
    with report.scenario(
        "`make dev` dev sign-in deletes the account",
        ["F4"],
        "AUTH_MODE=dev with the local service-role key; the dev user has no Supabase login",
    ) as scenario:
        api = api_factory(AUTH_MODE="dev")
        dev_user_id = str(uuid4())
        owned_data.seed(dev_user_id)

        response = _delete_account(api, f"dev:{dev_user_id}")
        scenario.check("DELETE /v1/account status", 200, response.status_code)
        scenario.check("DELETE /v1/account body", {"deleted": True}, response.json())
        scenario.check("dev user's data after deletion", DELETED, owned_data.counts(dev_user_id))


def test_dev_mode_without_key_deletes_account(report, api_factory, owned_data) -> None:
    with report.scenario(
        "Dev sign-in without Supabase admin access deletes the account",
        ["F9"],
        "AUTH_MODE=dev, SUPABASE_SERVICE_ROLE_KEY empty",
    ) as scenario:
        api = api_factory(AUTH_MODE="dev", SUPABASE_SERVICE_ROLE_KEY="")
        dev_user_id = str(uuid4())
        owned_data.seed(dev_user_id)

        response = _delete_account(api, f"dev:{dev_user_id}")
        scenario.check("DELETE /v1/account status", 200, response.status_code)
        scenario.check("DELETE /v1/account body", {"deleted": True}, response.json())
        scenario.check("dev user's data after deletion", DELETED, owned_data.counts(dev_user_id))


PRODUCTION_HOST = "api.mentioned.example.com"


def _production_env(**overrides: str) -> dict[str, str]:
    return _api_env(
        APP_ENV="production",
        DOCS_ENABLED="false",
        SOURCE_REQUIRE_HTTPS="true",
        CORS_ALLOWED_ORIGINS="https://mentioned.example.com",
        TRUSTED_HOSTS=PRODUCTION_HOST,
        **overrides,
    )


def test_production_api_refuses_to_boot_without_service_role_key(report) -> None:
    with report.scenario(
        "Production API boot without the service-role key",
        ["F3"],
        "Production settings, once with the key and once without",
    ) as scenario:
        # Control: the same production settings with the key boot, so a refusal below is
        # caused by the missing key and nothing else.
        process, base_url = _start_api(_production_env(), host=PRODUCTION_HOST)
        try:
            health = httpx.get(f"{base_url}/health", headers={"Host": PRODUCTION_HOST}, timeout=5)
            scenario.check("production API with the key is healthy", 200, health.status_code)
        finally:
            _stop_api(process)

        try:
            process, _ = _start_api(
                _production_env(SUPABASE_SERVICE_ROLE_KEY=""), host=PRODUCTION_HOST
            )
        except RuntimeError as exc:
            boot_output = str(exc)
        else:
            _stop_api(process)
            boot_output = "API booted and served /health"
        scenario.check(
            "production API without the key refuses to boot",
            True,
            "Production requires SUPABASE_SERVICE_ROLE_KEY" in boot_output,
        )
