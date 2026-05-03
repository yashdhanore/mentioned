from __future__ import annotations

from fastapi import HTTPException
import jwt
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from app.auth import _verify_supabase_token
from app.config import Settings, validate_settings
from app import db
from app.db import set_rls_user_context
from worker.run import _worker_database_url


def test_validate_settings_rejects_dev_auth_in_production() -> None:
    with pytest.raises(RuntimeError, match="Production requires AUTH_MODE=supabase"):
        validate_settings(Settings(app_env="production", auth_mode="dev"))


def _production_settings(**overrides: object) -> Settings:
    values = {
        "app_env": "production",
        "auth_mode": "supabase",
        "database_url": "postgresql://api:password@db.example.com:5432/postgres",
        "auto_create_tables": False,
        "docs_enabled": False,
        "cors_allowed_origins": ("https://app.example.com",),
        "trusted_hosts": ("api.example.com",),
        "source_require_https": True,
        "supabase_project_url": "https://example.supabase.co",
    }
    values.update(overrides)
    return Settings(**values)


def test_validate_settings_accepts_hardened_production_auth_config() -> None:
    validate_settings(_production_settings())


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"database_url": "sqlite:///app.db"}, "Production requires a PostgreSQL DATABASE_URL"),
        ({"auto_create_tables": True}, "Production requires AUTO_CREATE_TABLES=false"),
        ({"docs_enabled": True}, "Production requires DOCS_ENABLED=false"),
        ({"source_require_https": False}, "Production requires SOURCE_REQUIRE_HTTPS=true"),
        ({"cors_allowed_origins": ()}, "Production requires at least one CORS_ALLOWED_ORIGINS value"),
        (
            {"cors_allowed_origins": ("http://localhost:19006",)},
            "Production CORS_ALLOWED_ORIGINS must be non-local HTTPS origins",
        ),
        (
            {"cors_allowed_origins": ("https://",)},
            "Production CORS_ALLOWED_ORIGINS must be non-local HTTPS origins",
        ),
        ({"trusted_hosts": ()}, "Production requires at least one TRUSTED_HOSTS value"),
        ({"trusted_hosts": ("*",)}, "Production TRUSTED_HOSTS must be explicit non-local hosts"),
        ({"trusted_hosts": ("localhost:8000",)}, "Production TRUSTED_HOSTS must be explicit non-local hosts"),
        ({"trusted_hosts": ("https://api.example.com",)}, "Production TRUSTED_HOSTS must be explicit non-local hosts"),
        ({"supabase_project_url": None}, "Production requires SUPABASE_PROJECT_URL"),
    ],
)
def test_validate_settings_rejects_unsafe_production_auth_config(
    overrides: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(RuntimeError, match=message):
        validate_settings(_production_settings(**overrides))


def test_production_worker_requires_dedicated_database_url() -> None:
    settings = Settings(app_env="production", auth_mode="supabase", worker_database_url=None)

    with pytest.raises(RuntimeError, match="Production worker requires WORKER_DATABASE_URL"):
        _worker_database_url(settings)


def test_local_worker_defaults_to_api_database_url() -> None:
    settings = Settings(database_url="sqlite:///local.db", worker_database_url=None)

    assert _worker_database_url(settings) == "sqlite:///local.db"


def test_production_api_role_check_requires_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(db, "settings", Settings(app_env="production", auth_mode="supabase"))

    with pytest.raises(RuntimeError, match="Production API database must be PostgreSQL"):
        db.check_api_database_role(engine)


def test_supabase_token_verification_validates_authenticated_audience(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_decode(*args, **kwargs):
        captured.update(kwargs)
        return {"sub": "00000000-0000-4000-8000-000000000111"}

    monkeypatch.setattr("app.auth.jwt.get_unverified_header", lambda token: {"alg": "HS256"})
    monkeypatch.setattr("app.auth.jwt.decode", fake_decode)
    caller = _verify_supabase_token(
        "token",
        Settings(supabase_project_url="https://example.supabase.co", supabase_jwt_secret="secret"),
    )

    assert caller.subject_id == "00000000-0000-4000-8000-000000000111"
    assert captured["issuer"] == "https://example.supabase.co/auth/v1"
    assert captured["audience"] == "authenticated"


@pytest.mark.parametrize("role", ["anon", "service_role"])
def test_supabase_token_verification_rejects_non_user_roles(monkeypatch, role: str) -> None:
    def fake_decode(*args, **kwargs):
        return {"sub": "00000000-0000-4000-8000-000000000111", "role": role}

    monkeypatch.setattr("app.auth.jwt.get_unverified_header", lambda token: {"alg": "HS256"})
    monkeypatch.setattr("app.auth.jwt.decode", fake_decode)

    with pytest.raises(HTTPException) as exc_info:
        _verify_supabase_token(
            "token",
            Settings(supabase_project_url="https://example.supabase.co", supabase_jwt_secret="secret"),
        )

    assert exc_info.value.status_code == 401


def test_supabase_token_verification_rejects_missing_subject(monkeypatch) -> None:
    def fake_decode(*args, **kwargs):
        return {"role": "authenticated"}

    monkeypatch.setattr("app.auth.jwt.get_unverified_header", lambda token: {"alg": "HS256"})
    monkeypatch.setattr("app.auth.jwt.decode", fake_decode)

    with pytest.raises(HTTPException) as exc_info:
        _verify_supabase_token(
            "token",
            Settings(supabase_project_url="https://example.supabase.co", supabase_jwt_secret="secret"),
        )

    assert exc_info.value.status_code == 401


def test_supabase_token_verification_rejects_wrong_project(monkeypatch) -> None:
    def fake_decode(*args, **kwargs):
        raise jwt.InvalidIssuerError("wrong issuer")

    monkeypatch.setattr("app.auth.jwt.get_unverified_header", lambda token: {"alg": "HS256"})
    monkeypatch.setattr("app.auth.jwt.decode", fake_decode)

    with pytest.raises(HTTPException) as exc_info:
        _verify_supabase_token(
            "token",
            Settings(supabase_project_url="https://example.supabase.co", supabase_jwt_secret="secret"),
        )

    assert exc_info.value.status_code == 401


def test_set_rls_user_context_stores_verified_user_on_session() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with Session(engine) as session:
        set_rls_user_context(session, "00000000-0000-4000-8000-000000000111")

        assert session.info["rls_user_id"] == "00000000-0000-4000-8000-000000000111"


def test_supabase_es256_token_uses_jwks_even_when_legacy_secret_exists(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeSigningKey:
        key = "public-key"

    class FakeJwkClient:
        def __init__(self, url: str) -> None:
            captured["jwks_url"] = url

        def get_signing_key_from_jwt(self, token: str) -> FakeSigningKey:
            captured["jwks_token"] = token
            return FakeSigningKey()

    def fake_decode(*args, **kwargs):
        captured["key"] = args[1]
        captured.update(kwargs)
        return {"sub": "00000000-0000-4000-8000-000000000222"}

    monkeypatch.setattr("app.auth.jwt.get_unverified_header", lambda token: {"alg": "ES256"})
    monkeypatch.setattr("app.auth.PyJWKClient", FakeJwkClient)
    monkeypatch.setattr("app.auth.jwt.decode", fake_decode)

    caller = _verify_supabase_token(
        "token",
        Settings(supabase_project_url="https://example.supabase.co", supabase_jwt_secret="legacy-secret"),
    )

    assert caller.subject_id == "00000000-0000-4000-8000-000000000222"
    assert captured["jwks_url"] == "https://example.supabase.co/auth/v1/.well-known/jwks.json"
    assert captured["key"] == "public-key"
    assert captured["algorithms"] == ["ES256", "RS256"]
    assert captured["audience"] == "authenticated"
