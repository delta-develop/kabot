from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, call
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.pool import NullPool

from app.models.turn import Turn
from app.services.storage import relational_storage
from app.services.storage.relational_storage import RelationalStorage


def async_context_manager(value):
    manager = MagicMock()
    manager.__aenter__ = AsyncMock(return_value=value)
    manager.__aexit__ = AsyncMock(return_value=None)
    return manager


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def turn(
    seq: int = 0,
    session_id: str = "session-id",
    subject_id: str = "leo",
) -> Turn:
    return Turn(
        subject_id=subject_id,
        session_id=session_id,
        seq=seq,
        ts=NOW + timedelta(seconds=seq),
        user_text="hello",
        assistant_text="hi",
        embedding=[0.0] * 1536,
    )


@pytest.mark.asyncio
async def test_setup_bootstraps_vector_before_creating_the_main_schema(mocker):
    events = []
    bootstrap_connection = MagicMock()
    bootstrap_connection.execute = AsyncMock(
        side_effect=lambda _: events.append("extension")
    )
    bootstrap_engine = MagicMock()
    bootstrap_engine.begin.return_value = async_context_manager(bootstrap_connection)
    bootstrap_engine.dispose = AsyncMock(side_effect=lambda: events.append("dispose"))

    main_connection = MagicMock()
    main_connection.run_sync = AsyncMock(
        side_effect=lambda _: events.append("create_all")
    )
    main_engine = MagicMock()
    main_engine.begin.return_value = async_context_manager(main_connection)
    engines = iter([bootstrap_engine, main_engine])

    def create_engine_side_effect(*args, **kwargs):
        engine = next(engines)
        events.append(
            "bootstrap_engine" if engine is bootstrap_engine else "main_engine"
        )
        return engine

    create_engine = mocker.patch(
        "app.services.storage.relational_storage.create_async_engine",
        side_effect=create_engine_side_effect,
    )
    storage = RelationalStorage()
    await storage.setup()

    assert str(bootstrap_connection.execute.await_args.args[0]) == (
        "CREATE EXTENSION IF NOT EXISTS vector"
    )
    bootstrap_engine.dispose.assert_awaited_once()
    assert create_engine.call_args_list == [
        call(relational_storage.DATABASE_URL, poolclass=NullPool),
        call(relational_storage.DATABASE_URL),
    ]
    main_connection.run_sync.assert_awaited_once()
    assert events == [
        "bootstrap_engine",
        "extension",
        "dispose",
        "main_engine",
        "create_all",
    ]


@pytest.mark.asyncio
async def test_save_many_uses_plain_insert():
    session = MagicMock()
    session.begin.return_value = async_context_manager(None)
    storage = RelationalStorage()
    storage.session_local = MagicMock(return_value=async_context_manager(session))
    turns = [turn()]

    await storage.save_many(turns)

    session.add_all.assert_called_once_with(turns)
    session.begin.assert_called_once()


@pytest.mark.asyncio
async def test_history_orders_all_turns_oldest_first_with_tie_breakers():
    result = MagicMock()
    result.scalars.return_value.all.return_value = [turn(0), turn(1)]
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    storage = RelationalStorage()
    storage.session_local = MagicMock(return_value=async_context_manager(session))

    rows = await storage.history("leo")

    statement = session.execute.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "WHERE turn.subject_id" in sql
    assert "ORDER BY turn.ts ASC, turn.session_id ASC, turn.seq ASC" in sql
    assert "LIMIT" not in sql
    assert [row.seq for row in rows] == [0, 1]


@pytest.mark.asyncio
async def test_history_selects_latest_limited_turns_then_orders_them_oldest_first():
    result = MagicMock()
    result.scalars.return_value.all.return_value = [turn(1), turn(2)]
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    storage = RelationalStorage()
    storage.session_local = MagicMock(return_value=async_context_manager(session))

    rows = await storage.history("leo", limit=2)

    statement = session.execute.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ORDER BY turn.ts DESC, turn.session_id DESC, turn.seq DESC" in sql
    assert "ORDER BY turn.ts ASC, turn.session_id ASC, turn.seq ASC" in sql
    assert "LIMIT" in sql
    assert [row.seq for row in rows] == [1, 2]


def test_turn_schema_preserves_vector_and_unique_constraint():
    table = Turn.__table__

    assert table.c.embedding.type.dim == 1536
    assert any(
        constraint.name == "uq_turn_session_id_seq" for constraint in table.constraints
    )
    subject_index = next(
        index for index in table.indexes if index.name == "ix_turn_subject_id"
    )
    assert [column.name for column in subject_index.columns] == ["subject_id"]
    embedding_index = next(
        index for index in table.indexes if index.name == "ix_turn_embedding_hnsw"
    )
    assert embedding_index.dialect_options["postgresql"]["using"] == "hnsw"
    assert embedding_index.dialect_options["postgresql"]["ops"] == {
        "embedding": "vector_cosine_ops"
    }


@pytest.mark.asyncio
async def test_knn_search_isolates_subject_orders_and_omits_embedding():
    result = MagicMock()
    result.mappings.return_value.all.return_value = [
        {
            "id": UUID("00000000-0000-0000-0000-000000000001"),
            "subject_id": "leo",
            "session_id": "session-id",
            "seq": 0,
            "ts": datetime.now(UTC),
            "user_text": "hello",
            "assistant_text": "hi",
            "distance": 0.25,
        }
    ]
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    storage = RelationalStorage()
    storage.session_local = MagicMock(return_value=async_context_manager(session))

    rows = await storage.knn_search("leo", [0.0] * 1536, k=3)

    statement = session.execute.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "WHERE turn.subject_id" in sql
    assert "<=>" in sql
    assert "ORDER BY distance ASC" in sql
    assert "embedding" not in rows[0]
    assert rows[0]["id"] == "00000000-0000-0000-0000-000000000001"
    assert rows[0]["subject_id"] == "leo"


@pytest.mark.parametrize("k", [0, 101])
@pytest.mark.asyncio
async def test_knn_search_rejects_k_outside_contract(k):
    with pytest.raises(ValueError, match="k must be between 1 and 100"):
        await RelationalStorage().knn_search("leo", [0.0] * 1536, k=k)
