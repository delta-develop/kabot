from unittest.mock import AsyncMock, MagicMock, call
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.pool import NullPool

from app.services.storage import relational_storage
from app.services.storage.relational_storage import RelationalStorage


def async_context_manager(value):
    manager = MagicMock()
    manager.__aenter__ = AsyncMock(return_value=value)
    manager.__aexit__ = AsyncMock(return_value=None)
    return manager


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
async def test_upsert_items_updates_content_but_preserves_id():
    session = MagicMock()
    session.begin.return_value = async_context_manager(None)
    session.execute = AsyncMock()
    session_factory = MagicMock(return_value=async_context_manager(session))
    storage = RelationalStorage()
    storage.session_local = session_factory
    item = {
        "namespace": "restaurant-supplies",
        "external_id": "sku-1",
        "title": "Salt",
        "body": "Fine salt",
        "attributes": {"store": "abarrotes"},
        "embedding": [0.0] * 1536,
    }

    await storage.upsert_items([item])

    statement = session.execute.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (namespace, external_id) DO UPDATE" in sql
    assert "title = excluded.title" in sql
    assert "body = excluded.body" in sql
    assert "attributes = excluded.attributes" in sql
    assert "embedding = excluded.embedding" in sql
    assert "id = excluded.id" not in sql
    session.begin.assert_called_once()


@pytest.mark.asyncio
async def test_knn_search_scopes_filters_orders_and_shapes_results():
    result = MagicMock()
    result.mappings.return_value.all.return_value = [
        {
            "id": UUID("00000000-0000-0000-0000-000000000001"),
            "namespace": "restaurant-supplies",
            "external_id": "sku-1",
            "title": "Salt",
            "body": "Fine salt",
            "attributes": {"store": "abarrotes"},
            "distance": 0.25,
        }
    ]
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    storage = RelationalStorage()
    storage.session_local = MagicMock(return_value=async_context_manager(session))

    rows = await storage.knn_search(
        "restaurant-supplies",
        [0.0] * 1536,
        filters={"store": "abarrotes"},
        k=3,
    )

    statement = session.execute.await_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "catalog_item.namespace" in sql
    assert "<=>" in sql
    assert "ORDER BY distance ASC" in sql
    assert 3 in compiled.params.values()
    assert "embedding" not in rows[0]
    assert rows == [
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "namespace": "restaurant-supplies",
            "external_id": "sku-1",
            "title": "Salt",
            "body": "Fine salt",
            "attributes": {"store": "abarrotes"},
            "distance": 0.25,
        }
    ]


@pytest.mark.parametrize("k", [0, 101])
@pytest.mark.asyncio
async def test_knn_search_rejects_k_outside_contract(k):
    storage = RelationalStorage()

    with pytest.raises(ValueError, match="k must be between 1 and 100"):
        await storage.knn_search("restaurant-supplies", [0.0] * 1536, k=k)
