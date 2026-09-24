from __future__ import annotations

import src.config

# get_settings() loads the developer's .env into os.environ, which then leaks into every
# later Settings() in the session; CI has no .env, so tests must not depend on one either.
src.config.load_dotenv = lambda *args, **kwargs: False

import os

# No test may send traces to Langfuse Cloud, even with keys in the shell; the tracing E2E suite
# turns this back on for its fake Langfuse server.
os.environ["LANGFUSE_TRACING_ENABLED"] = "false"

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from src.auth.dependencies import get_current_caller
from src.auth.schemas import Caller
from src.database import get_session
from src.main import app

TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TEST_USER_ID = "00000000-0000-4000-8000-000000000001"


def _test_caller() -> Caller:
    return Caller(subject_id=TEST_USER_ID, role="user")


def _test_session():
    with Session(TEST_ENGINE) as session:
        yield session


@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.create_all(TEST_ENGINE)
    yield
    SQLModel.metadata.drop_all(TEST_ENGINE)


@pytest.fixture
def session():
    with Session(TEST_ENGINE) as session:
        yield session


@pytest.fixture
async def client():
    app.dependency_overrides[get_current_caller] = _test_caller
    app.dependency_overrides[get_session] = _test_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
