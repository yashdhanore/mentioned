from __future__ import annotations

from app.auth import _verify_supabase_token
from app.config import Settings


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
