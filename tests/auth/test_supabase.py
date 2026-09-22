from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi import HTTPException
from jwt import PyJWKClient
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

from src.auth.supabase import _jwks_client, verify_supabase_token
from src.config import AuthConfig

PROJECT_URL = "https://project.supabase.co"
ISSUER = PROJECT_URL + "/auth/v1"
JWKS_URL = ISSUER + "/.well-known/jwks.json"
AUDIENCE = "authenticated"
RSA_KID = "rsa-key-1"
EC_KID = "ec-key-1"


def _config(supabase_jwt_secret: str | None = None) -> AuthConfig:
    return AuthConfig(
        supabase_project_url=PROJECT_URL,
        supabase_jwt_audience=AUDIENCE,
        supabase_jwt_secret=supabase_jwt_secret,
    )


@pytest.fixture(autouse=True)
def clear_jwks_cache():
    _jwks_client.cache_clear()
    yield
    _jwks_client.cache_clear()


@pytest.fixture
def rsa_private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def ec_private_key():
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def jwks_fetch_count(monkeypatch, rsa_private_key, ec_private_key):
    rsa_jwk = RSAAlgorithm.to_jwk(rsa_private_key.public_key(), as_dict=True)
    rsa_jwk.update({"kid": RSA_KID, "use": "sig", "alg": "RS256"})
    ec_jwk = ECAlgorithm.to_jwk(ec_private_key.public_key(), as_dict=True)
    ec_jwk.update({"kid": EC_KID, "use": "sig", "alg": "ES256"})
    jwk_set = {"keys": [rsa_jwk, ec_jwk]}

    counter = {"count": 0}

    def fake_fetch_data(self):
        counter["count"] += 1
        return jwk_set

    monkeypatch.setattr(PyJWKClient, "fetch_data", fake_fetch_data)
    return counter


def _claims(**overrides) -> dict:
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": str(uuid.uuid4()),
        "role": "authenticated",
        "exp": int(time.time()) + 3600,
    }
    claims.update(overrides)
    return claims


def _token(private_key, algorithm: str, kid: str, claims: dict) -> str:
    return jwt.encode(claims, private_key, algorithm=algorithm, headers={"kid": kid})


def test_valid_rs256_token(jwks_fetch_count, rsa_private_key):
    claims = _claims()
    token = _token(rsa_private_key, "RS256", RSA_KID, claims)

    caller = verify_supabase_token(token, _config())

    assert caller.subject_id == claims["sub"]
    assert caller.role == "user"


def test_valid_es256_token(jwks_fetch_count, ec_private_key):
    claims = _claims()
    token = _token(ec_private_key, "ES256", EC_KID, claims)

    caller = verify_supabase_token(token, _config())

    assert caller.subject_id == claims["sub"]
    assert caller.role == "user"


def test_wrong_audience_rejected(jwks_fetch_count, rsa_private_key):
    token = _token(rsa_private_key, "RS256", RSA_KID, _claims(aud="some-other-app"))

    with pytest.raises(HTTPException) as excinfo:
        verify_supabase_token(token, _config())

    assert excinfo.value.status_code == 401


def test_wrong_issuer_rejected(jwks_fetch_count, rsa_private_key):
    token = _token(
        rsa_private_key,
        "RS256",
        RSA_KID,
        _claims(iss="https://not-the-project.supabase.co/auth/v1"),
    )

    with pytest.raises(HTTPException) as excinfo:
        verify_supabase_token(token, _config())

    assert excinfo.value.status_code == 401


def test_expired_token_rejected(jwks_fetch_count, rsa_private_key):
    token = _token(
        rsa_private_key,
        "RS256",
        RSA_KID,
        _claims(exp=int(time.time()) - 3600),
    )

    with pytest.raises(HTTPException) as excinfo:
        verify_supabase_token(token, _config())

    assert excinfo.value.status_code == 401


def test_unknown_kid_rejected(jwks_fetch_count, rsa_private_key):
    token = _token(rsa_private_key, "RS256", "unknown-kid", _claims())

    with pytest.raises(HTTPException) as excinfo:
        verify_supabase_token(token, _config())

    assert excinfo.value.status_code == 401


def test_alg_none_rejected(jwks_fetch_count):
    unverified = jwt.encode(_claims(), key=None, algorithm="none")

    with pytest.raises(HTTPException) as excinfo:
        verify_supabase_token(unverified, _config())

    assert excinfo.value.status_code == 401


def test_hs256_algorithm_confusion_rejected(jwks_fetch_count, rsa_private_key):
    public_pem = rsa_private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    def b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    # A real attacker wouldn't go through PyJWT's encode(), which itself refuses to
    # use a PEM-looking key as an HMAC secret. Forge the raw HS256 token bytes
    # directly to prove the server-side algorithm separation, not PyJWT's guard rail.
    header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = b64url(json.dumps(_claims()).encode())
    signing_input = f"{header}.{payload}".encode()
    signature = hmac.new(public_pem, signing_input, hashlib.sha256).digest()
    forged_token = f"{header}.{payload}.{b64url(signature)}"

    with pytest.raises(HTTPException) as excinfo:
        verify_supabase_token(
            forged_token, _config(supabase_jwt_secret="real-server-only-secret-at-least-32-bytes")
        )

    assert excinfo.value.status_code == 401


def test_missing_sub_rejected(jwks_fetch_count, rsa_private_key):
    claims = _claims()
    del claims["sub"]
    token = _token(rsa_private_key, "RS256", RSA_KID, claims)

    with pytest.raises(HTTPException) as excinfo:
        verify_supabase_token(token, _config())

    assert excinfo.value.status_code == 401


def test_jwks_fetched_once_across_two_verifications(jwks_fetch_count, rsa_private_key):
    claims_a = _claims()
    claims_b = _claims()
    token_a = _token(rsa_private_key, "RS256", RSA_KID, claims_a)
    token_b = _token(rsa_private_key, "RS256", RSA_KID, claims_b)

    verify_supabase_token(token_a, _config())
    verify_supabase_token(token_b, _config())

    assert jwks_fetch_count["count"] == 1
