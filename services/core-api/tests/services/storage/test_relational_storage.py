from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, call

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.pool import NullPool

from app.models import turn as turn_models
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
async def test_has_turns_checks_subject_existence():
    result = MagicMock()
    result.scalar.return_value = True
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    storage = RelationalStorage()
    storage.session_local = MagicMock(return_value=async_context_manager(session))

    assert await storage.has_turns("leo") is True

    statement = session.execute.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "SELECT EXISTS" in sql
    assert "WHERE turn.subject_id" in sql


def test_fragment_shape():
    item = turn()

    fragment = turn_models.Fragment(
        turns=[item],
        session_id=item.session_id,
        ts=item.ts,
        similarity=0.75,
    )

    assert fragment.turns == [item]
    assert fragment.session_id == "session-id"
    assert fragment.ts == item.ts
    assert fragment.similarity == 0.75


@pytest.mark.asyncio
async def test_similar_excludes_session_and_fetches_neighbors_in_one_query():
    set_result = MagicMock()
    hits_result = MagicMock()
    hits_result.mappings.return_value.all.return_value = [
        {"session_id": "past", "seq": 1, "distance": 0.1}
    ]
    neighbors_result = MagicMock()
    neighbors_result.scalars.return_value.all.return_value = [
        turn(2, "past"),
        turn(0, "past"),
        turn(1, "past"),
    ]
    session = MagicMock()
    session.begin.return_value = async_context_manager(None)
    session.execute = AsyncMock(side_effect=[set_result, hits_result, neighbors_result])
    storage = RelationalStorage()
    storage.session_local = MagicMock(return_value=async_context_manager(session))

    fragments = await storage.similar(
        "leo", [0.0] * 1536, k=3, exclude_session="current"
    )

    assert session.execute.await_count == 3
    assert str(session.execute.await_args_list[0].args[0]) == (
        "SET LOCAL hnsw.iterative_scan = relaxed_order"
    )
    hits_sql = str(
        session.execute.await_args_list[1].args[0].compile(dialect=postgresql.dialect())
    )
    assert "turn.subject_id" in hits_sql
    assert "turn.session_id !=" in hits_sql
    assert "ORDER BY distance ASC" in hits_sql
    assert "LIMIT" in hits_sql
    neighbors_sql = str(
        session.execute.await_args_list[2].args[0].compile(dialect=postgresql.dialect())
    )
    assert "(turn.session_id, turn.seq) IN" in neighbors_sql
    assert len(fragments) == 1
    assert [item.seq for item in fragments[0].turns] == [0, 1, 2]
    assert fragments[0].similarity == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_similar_threshold_can_remove_all_hits(monkeypatch):
    monkeypatch.setattr(relational_storage, "RECALL_MIN_SIMILARITY", 0.8)
    hits_result = MagicMock()
    hits_result.mappings.return_value.all.return_value = [
        {"session_id": "past", "seq": 1, "distance": 0.3}
    ]
    session = MagicMock()
    session.begin.return_value = async_context_manager(None)
    session.execute = AsyncMock(side_effect=[MagicMock(), hits_result])
    storage = RelationalStorage()
    storage.session_local = MagicMock(return_value=async_context_manager(session))

    assert await storage.similar("leo", [0.0] * 1536, k=1) == []
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_similar_window_zero_keeps_adjacent_hits_separate(monkeypatch):
    monkeypatch.setattr(relational_storage, "RECALL_WINDOW", 0)
    hits_result = MagicMock()
    hits_result.mappings.return_value.all.return_value = [
        {"session_id": "past", "seq": 1, "distance": 0.1},
        {"session_id": "past", "seq": 2, "distance": 0.2},
    ]
    neighbors_result = MagicMock()
    neighbors_result.scalars.return_value.all.return_value = [
        turn(1, "past"),
        turn(2, "past"),
    ]
    session = MagicMock()
    session.begin.return_value = async_context_manager(None)
    session.execute = AsyncMock(
        side_effect=[MagicMock(), hits_result, neighbors_result]
    )
    storage = RelationalStorage()
    storage.session_local = MagicMock(return_value=async_context_manager(session))

    fragments = await storage.similar("leo", [0.0] * 1536, k=2)

    assert [[item.seq for item in fragment.turns] for fragment in fragments] == [
        [1],
        [2],
    ]


@pytest.mark.asyncio
async def test_similar_merges_overlapping_windows_without_duplicate_turns():
    hits_result = MagicMock()
    hits_result.mappings.return_value.all.return_value = [
        {"session_id": "past", "seq": 1, "distance": 0.1},
        {"session_id": "past", "seq": 2, "distance": 0.2},
    ]
    neighbors_result = MagicMock()
    neighbors_result.scalars.return_value.all.return_value = [
        turn(seq, "past") for seq in range(4)
    ]
    session = MagicMock()
    session.begin.return_value = async_context_manager(None)
    session.execute = AsyncMock(
        side_effect=[MagicMock(), hits_result, neighbors_result]
    )
    storage = RelationalStorage()
    storage.session_local = MagicMock(return_value=async_context_manager(session))

    fragments = await storage.similar("leo", [0.0] * 1536, k=2)

    assert len(fragments) == 1
    assert [item.seq for item in fragments[0].turns] == [0, 1, 2, 3]
    assert fragments[0].similarity == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_similar_orders_fragments_by_relevance(monkeypatch):
    monkeypatch.setattr(relational_storage, "RECALL_WINDOW", 0)
    hits_result = MagicMock()
    hits_result.mappings.return_value.all.return_value = [
        {"session_id": "less-relevant", "seq": 0, "distance": 0.4},
        {"session_id": "more-relevant", "seq": 0, "distance": 0.1},
    ]
    neighbors_result = MagicMock()
    neighbors_result.scalars.return_value.all.return_value = [
        turn(0, "less-relevant"),
        turn(0, "more-relevant"),
    ]
    session = MagicMock()
    session.begin.return_value = async_context_manager(None)
    session.execute = AsyncMock(
        side_effect=[MagicMock(), hits_result, neighbors_result]
    )
    storage = RelationalStorage()
    storage.session_local = MagicMock(return_value=async_context_manager(session))

    fragments = await storage.similar("leo", [0.0] * 1536, k=2)

    assert [fragment.session_id for fragment in fragments] == [
        "more-relevant",
        "less-relevant",
    ]
    assert [fragment.similarity for fragment in fragments] == pytest.approx([0.9, 0.6])


@pytest.mark.parametrize("k", [0, 101])
@pytest.mark.asyncio
async def test_similar_rejects_k_outside_contract(k):
    with pytest.raises(ValueError, match="k must be between 1 and 100"):
        await RelationalStorage().similar("leo", [0.0] * 1536, k=k)


@pytest.mark.asyncio
async def test_similar_rejects_negative_recall_window(monkeypatch):
    monkeypatch.setattr(relational_storage, "RECALL_WINDOW", -1)

    with pytest.raises(ValueError, match="RECALL_WINDOW must be zero or greater"):
        await RelationalStorage().similar("leo", [0.0] * 1536, k=1)
