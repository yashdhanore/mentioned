from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import event, text
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


settings = get_settings()
database_url = normalize_database_url(settings.database_url)

if database_url.startswith("sqlite"):
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
else:
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
    )


def _set_connection_rls_user(connection, owner_id: str) -> None:
    connection.execute(
        text("select set_config('app.current_user_id', :owner_id, true)"),
        {"owner_id": owner_id},
    )


@event.listens_for(SQLAlchemySession, "after_begin")
def _apply_rls_user_context(session, _transaction, connection) -> None:
    owner_id = session.info.get("rls_user_id")
    if not isinstance(owner_id, str) or not owner_id:
        return
    if connection.dialect.name != "postgresql":
        return
    _set_connection_rls_user(connection, owner_id)


def set_rls_user_context(session: Session, owner_id: str) -> None:
    session.info["rls_user_id"] = owner_id
    if session.in_transaction() and session.bind and session.bind.dialect.name == "postgresql":
        session.execute(
            text("select set_config('app.current_user_id', :owner_id, true)"),
            {"owner_id": owner_id},
        )


def create_db_and_tables() -> None:
    if not settings.auto_create_tables:
        return
    SQLModel.metadata.create_all(engine)


def check_database_ready() -> None:
    with engine.connect() as connection:
        connection.execute(text("select 1"))


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
