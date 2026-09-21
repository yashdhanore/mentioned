from __future__ import annotations

from sqlmodel import select

from src.waitlist.models import WaitlistSignup


async def test_create_waitlist_signup_is_public(client, session):
    resp = await client.post(
        "/v1/waitlist",
        json={"email": "Reader@Example.com", "source": "landing-page"},
        headers={"user-agent": "pytest"},
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "reader@example.com"
    assert data["created"] is True
    # Pin the wire format: aware UTC datetimes serialize with an explicit "Z"
    # offset, not a bare "YYYY-MM-DDTHH:MM:SS" with no timezone designator.
    assert data["created_at"].endswith("Z")

    signup = session.exec(select(WaitlistSignup)).one()
    assert signup.email == "reader@example.com"
    assert signup.source == "landing-page"
    assert signup.user_agent == "pytest"
    assert signup.created_at.tzinfo is not None


async def test_create_waitlist_signup_is_idempotent(client, session):
    first_resp = await client.post(
        "/v1/waitlist",
        json={"email": "reader@example.com", "source": "landing-page"},
    )
    second_resp = await client.post(
        "/v1/waitlist",
        json={"email": "READER@example.com", "source": "footer-cta"},
    )

    assert first_resp.status_code == 201
    assert second_resp.status_code == 200
    assert second_resp.json()["id"] == first_resp.json()["id"]
    assert second_resp.json()["created"] is False

    signups = list(session.exec(select(WaitlistSignup)).all())
    assert len(signups) == 1
    assert signups[0].source == "footer-cta"


async def test_create_waitlist_signup_rejects_invalid_email(client):
    resp = await client.post("/v1/waitlist", json={"email": "not-an-email"})

    assert resp.status_code == 422
    assert resp.json() == {
        "error_code": "validation_error",
        "message": "The request is not valid.",
    }
