from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import text
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
