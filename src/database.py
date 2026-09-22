from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlmodel import Session, SQLModel, create_engine

from src.config import get_settings


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def create_sql_engine(database_url: str) -> Engine:
    normalized_url = normalize_database_url(database_url)
    if normalized_url.startswith("sqlite"):
        return create_engine(normalized_url, connect_args={"check_same_thread": False})
    return create_engine(
        normalized_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
    )


settings = get_settings()
engine = create_sql_engine(settings.database_url)

_SET_RLS_USER_SQL = text("select set_config('app.current_user_id', :owner_id, true)")


@event.listens_for(SQLAlchemySession, "after_begin")
def _apply_rls_user_context(session, _transaction, connection) -> None:
    owner_id = session.info.get("rls_user_id")
    if not isinstance(owner_id, str) or not owner_id:
        return
    if connection.dialect.name != "postgresql":
        return
    connection.execute(_SET_RLS_USER_SQL, {"owner_id": owner_id})


def set_rls_user_context(session: Session, owner_id: str) -> None:
    session.info["rls_user_id"] = owner_id
    if session.in_transaction() and session.bind and session.bind.dialect.name == "postgresql":
        session.execute(_SET_RLS_USER_SQL, {"owner_id": owner_id})


def create_db_and_tables(bind: Engine | None = None) -> None:
    if not settings.db.auto_create_tables:
        return
    SQLModel.metadata.create_all(bind or engine)


def _database_role_flags(bind: Engine) -> dict[str, object]:
    with bind.connect() as connection:
        return dict(
            connection.execute(
                text(
                    """
                    select current_user, rolsuper, rolbypassrls
                    from pg_roles
                    where rolname = current_user
                    """
                )
            )
            .mappings()
            .one()
        )


def _check_non_privileged_database_role(bind: Engine, *, label: str) -> None:
    if bind.dialect.name != "postgresql":
        raise RuntimeError(f"Production {label} database must be PostgreSQL")
    row = _database_role_flags(bind)
    if row["rolsuper"] or row["rolbypassrls"]:
        raise RuntimeError(
            f"Production {label} database role must be non-superuser and must not BYPASSRLS"
        )


def check_api_database_role(bind: Engine | None = None) -> None:
    if not settings.is_production:
        return
    _check_non_privileged_database_role(bind or engine, label="API")


def check_worker_database_role(bind: Engine, *, require_postgres: bool = False) -> None:
    if bind.dialect.name != "postgresql":
        if require_postgres:
            raise RuntimeError("Production worker database must be PostgreSQL")
        return
    _check_non_privileged_database_role(bind, label="worker")


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
