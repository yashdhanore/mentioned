from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from src.waitlist.models import WaitlistSignup


def normalize_waitlist_email(email: str) -> str:
    return email.strip().casefold()


def create_or_update_signup(
    session: Session,
    *,
    email: str,
    source: str | None = None,
    user_agent: str | None = None,
) -> tuple[WaitlistSignup, bool]:
    normalized_email = normalize_waitlist_email(email)
    signup = session.exec(
        select(WaitlistSignup).where(WaitlistSignup.email == normalized_email)
    ).first()

    if signup:
        signup.source = source or signup.source
        signup.user_agent = user_agent or signup.user_agent
        signup.updated_at = datetime.utcnow()
        session.add(signup)
        session.commit()
        session.refresh(signup)
        return signup, False

    signup = WaitlistSignup(
        email=normalized_email,
        source=source,
        user_agent=user_agent,
    )
    session.add(signup)
    session.commit()
    session.refresh(signup)
    return signup, True
