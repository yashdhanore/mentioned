from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from sqlalchemy import event
from sqlmodel import Session

from src.sources.models import SavedSource, Source, SourceItem, SourceStatus
from src.sources.read_models import saved_source_list_response

OWNER = "00000000-0000-4000-8000-000000000001"
OWNER_UUID = UUID(OWNER)


def _create_saved_source(session: Session, external_id: str, item_count: int = 2) -> None:
    source = Source(
        source_key=f"instagram:reel:{external_id}",
        platform="instagram",
        source_type="reel",
        external_id=external_id,
        canonical_url=f"https://www.instagram.com/reel/{external_id}/",
        status=SourceStatus.DONE,
    )
    session.add(source)
    session.commit()
    session.refresh(source)

    session.add(SavedSource(owner_id=OWNER_UUID, source_id=source.id))
    session.commit()

    for position in range(item_count):
        session.add(
            SourceItem(
                source_id=source.id,
                category="book",
                title=f"{external_id} item {position}",
                position=position,
            )
        )
    session.commit()


def _count_statements(session: Session, fn: Callable[[], None]) -> int:
    count = 0

    def _listener(*_args, **_kwargs) -> None:
        nonlocal count
        count += 1

    engine = session.get_bind()
    event.listen(engine, "before_cursor_execute", _listener)
    try:
        fn()
    finally:
        event.remove(engine, "before_cursor_execute", _listener)
    return count


def test_saved_source_list_response_query_count_does_not_grow_with_saved_sources(
    session: Session,
) -> None:
    for i in range(3):
        _create_saved_source(session, f"SMALL{i}")

    small_count = _count_statements(
        session, lambda: saved_source_list_response(session, OWNER, limit=50)
    )

    for i in range(20):
        _create_saved_source(session, f"LARGE{i}")

    large_count = _count_statements(
        session, lambda: saved_source_list_response(session, OWNER, limit=50)
    )

    assert small_count == 2
    assert large_count == 2
