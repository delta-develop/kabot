import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymongo import AsyncMongoClient

import app.services.storage.connections as connections_module
from app.services.storage.connections import get_mongo_client
from app.services.storage.non_relational_storage import NonRelationalStorage


@pytest.mark.asyncio
async def test_get_mongo_client_returns_async_mongo_client(monkeypatch):
    monkeypatch.setattr(connections_module, "_mongo_client", None)
    client = await get_mongo_client()
    assert isinstance(client, AsyncMongoClient)


@pytest.mark.asyncio
async def test_get_mongo_client_singleton(monkeypatch):
    monkeypatch.setattr(connections_module, "_mongo_client", None)
    client1 = await get_mongo_client()
    client2 = await get_mongo_client()
    assert client1 is client2


@pytest.mark.skipif(not os.getenv("MONGO_URL"), reason="MONGO_URL is not configured")
@pytest.mark.asyncio
async def test_real_mongo_is_reachable(monkeypatch):
    monkeypatch.setattr(connections_module, "_mongo_client", None)
    client = await get_mongo_client()

    result = await client.admin.command("ping")

    assert result["ok"] == 1


@pytest.mark.asyncio
async def test_non_relational_storage_setup(mocker):
    mock_coll = MagicMock()
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_coll
    mock_client = MagicMock()
    mock_client.get_default_database.return_value = mock_db
    mocker.patch(
        "app.services.storage.non_relational_storage.get_mongo_client",
        AsyncMock(return_value=mock_client),
    )

    storage = NonRelationalStorage(collection_name="fact_memory")
    await storage.setup()
    assert storage.collection == mock_coll
    mock_db.__getitem__.assert_called_once_with("fact_memory")


@pytest.mark.asyncio
async def test_save_replaces_keyed_document(mocker):
    mock_coll = MagicMock()
    mock_coll.replace_one = AsyncMock()
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_coll
    mock_client = MagicMock()
    mock_client.get_default_database.return_value = mock_db
    mocker.patch(
        "app.services.storage.non_relational_storage.get_mongo_client",
        AsyncMock(return_value=mock_client),
    )

    storage = NonRelationalStorage(collection_name="fact_memory")
    document = {"subject_id": "user_123", "facts": {"name": "Alice"}}
    await storage.save(document)

    mock_coll.replace_one.assert_awaited_once_with(
        {"subject_id": "user_123"}, document, upsert=True
    )


@pytest.mark.asyncio
async def test_get_and_delete_operations(mocker):
    mock_coll = MagicMock()
    mock_coll.find_one = AsyncMock(return_value={"subject_id": "user_123", "facts": {}})
    mock_coll.delete_one = AsyncMock()
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_coll
    mock_client = MagicMock()
    mock_client.get_default_database.return_value = mock_db
    mocker.patch(
        "app.services.storage.non_relational_storage.get_mongo_client",
        AsyncMock(return_value=mock_client),
    )

    storage = NonRelationalStorage(collection_name="fact_memory")
    doc = await storage.get({"subject_id": "user_123"})
    assert doc == {"subject_id": "user_123", "facts": {}}
    mock_coll.find_one.assert_awaited_once_with(
        {"subject_id": "user_123"}, projection={"_id": 0}
    )

    await storage.delete("user_123")
    mock_coll.delete_one.assert_awaited_once_with({"subject_id": "user_123"})
