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


@pytest.mark.asyncio
async def test_non_relational_storage_invalid_collection():
    storage = NonRelationalStorage(collection_name="unknown_collection")
    with pytest.raises(ValueError, match="Invalid collection name"):
        await storage.save({"whatsapp_id": "123", "data": "test"})


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

    storage = NonRelationalStorage(collection_name="episodic_memory")
    await storage.setup()
    assert storage.collection == mock_coll
    mock_db.__getitem__.assert_called_once_with("episodic_memory")


@pytest.mark.asyncio
async def test_save_episodic_memory_fifo_semantics(mocker):
    mock_coll = MagicMock()
    mock_coll.update_one = AsyncMock()
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_coll
    mock_client = MagicMock()
    mock_client.get_default_database.return_value = mock_db
    mocker.patch(
        "app.services.storage.non_relational_storage.get_mongo_client",
        AsyncMock(return_value=mock_client),
    )

    storage = NonRelationalStorage(collection_name="episodic_memory")
    messages = [
        {"role": "user", "content": "first message"},
        {"role": "assistant", "content": "second message"},
    ]
    await storage.save({"whatsapp_id": "user_123", "data": messages})

    mock_coll.update_one.assert_awaited_once()
    args, kwargs = mock_coll.update_one.call_args
    assert args[0] == {"whatsapp_id": "user_123"}
    update_op = args[1]
    assert "$push" in update_op
    assert update_op["$push"] == {"history": {"$each": messages}}
    assert "$set" in update_op
    assert "last_updated" in update_op["$set"]
    assert kwargs.get("upsert") is True


@pytest.mark.asyncio
async def test_save_episodic_memory_invalid_data_raises():
    storage = NonRelationalStorage(collection_name="episodic_memory")
    with pytest.raises(ValueError, match="EpisodicMemory expects `data` to be a list"):
        await storage.save({"whatsapp_id": "user_123", "data": "not a list"})


@pytest.mark.asyncio
async def test_save_fact_memory_semantics(mocker):
    mock_coll = MagicMock()
    mock_coll.update_one = AsyncMock()
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_coll
    mock_client = MagicMock()
    mock_client.get_default_database.return_value = mock_db
    mocker.patch(
        "app.services.storage.non_relational_storage.get_mongo_client",
        AsyncMock(return_value=mock_client),
    )

    storage = NonRelationalStorage(collection_name="fact_memory")
    facts_data = {"name": "Alice", "preferred_brand": "Toyota"}
    await storage.save({"whatsapp_id": "user_123", "data": facts_data})

    mock_coll.update_one.assert_awaited_once()
    args, kwargs = mock_coll.update_one.call_args
    assert args[0] == {"whatsapp_id": "user_123"}
    update_op = args[1]
    assert "$set" in update_op
    assert update_op["$set"]["facts"] == facts_data
    assert "last_updated" in update_op["$set"]
    assert kwargs.get("upsert") is True


@pytest.mark.asyncio
async def test_save_summary_memory_semantics(mocker):
    mock_coll = MagicMock()
    mock_coll.update_one = AsyncMock()
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_coll
    mock_client = MagicMock()
    mock_client.get_default_database.return_value = mock_db
    mocker.patch(
        "app.services.storage.non_relational_storage.get_mongo_client",
        AsyncMock(return_value=mock_client),
    )

    storage = NonRelationalStorage(collection_name="summary_memory")
    summary_data = "User is interested in sedans."
    await storage.save({"whatsapp_id": "user_123", "data": summary_data})

    mock_coll.update_one.assert_awaited_once()
    args, kwargs = mock_coll.update_one.call_args
    assert args[0] == {"whatsapp_id": "user_123"}
    update_op = args[1]
    assert "$set" in update_op
    assert update_op["$set"]["summary"] == summary_data
    assert "last_updated" in update_op["$set"]
    assert kwargs.get("upsert") is True


@pytest.mark.asyncio
async def test_get_and_delete_operations(mocker):
    mock_coll = MagicMock()
    mock_coll.find_one = AsyncMock(
        return_value={"whatsapp_id": "user_123", "history": []}
    )
    mock_coll.delete_one = AsyncMock()
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_coll
    mock_client = MagicMock()
    mock_client.get_default_database.return_value = mock_db
    mocker.patch(
        "app.services.storage.non_relational_storage.get_mongo_client",
        AsyncMock(return_value=mock_client),
    )

    storage = NonRelationalStorage(collection_name="episodic_memory")
    doc = await storage.get({"whatsapp_id": "user_123"})
    assert doc == {"whatsapp_id": "user_123", "history": []}
    mock_coll.find_one.assert_awaited_once_with(
        {"whatsapp_id": "user_123"}, projection={"_id": 0}
    )

    await storage.delete("user_123")
    mock_coll.delete_one.assert_awaited_once_with({"whatsapp_id": "user_123"})


@pytest.mark.asyncio
async def test_episodic_memory_write_then_read_fifo_order(mocker):
    """Verify that successive writes to episodic_memory preserve FIFO message order when read."""
    documents = {}

    mock_coll = MagicMock()

    async def fake_update_one(filter_dict, update_doc, upsert=False):
        key = filter_dict["whatsapp_id"]
        doc = documents.setdefault(key, {"whatsapp_id": key, "history": []})
        if "$push" in update_doc and "history" in update_doc["$push"]:
            each_messages = update_doc["$push"]["history"]["$each"]
            doc["history"].extend(each_messages)
        if "$set" in update_doc:
            for k, v in update_doc["$set"].items():
                doc[k] = v

    async def fake_find_one(filter_dict, projection=None):
        key = filter_dict["whatsapp_id"]
        if key not in documents:
            return None
        doc = dict(documents[key])
        if projection and projection.get("_id") == 0:
            doc.pop("_id", None)
        return doc

    mock_coll.update_one = AsyncMock(side_effect=fake_update_one)
    mock_coll.find_one = AsyncMock(side_effect=fake_find_one)
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_coll
    mock_client = MagicMock()
    mock_client.get_default_database.return_value = mock_db
    mocker.patch(
        "app.services.storage.non_relational_storage.get_mongo_client",
        AsyncMock(return_value=mock_client),
    )

    storage = NonRelationalStorage(collection_name="episodic_memory")

    # First write batch
    batch1 = [
        {"role": "user", "content": "Msg 1"},
        {"role": "assistant", "content": "Msg 2"},
    ]
    await storage.save({"whatsapp_id": "user_fifo", "data": batch1})

    # Second write batch
    batch2 = [{"role": "user", "content": "Msg 3"}]
    await storage.save({"whatsapp_id": "user_fifo", "data": batch2})

    # Read back and check order
    result = await storage.get({"whatsapp_id": "user_fifo"})
    assert result is not None
    assert result["history"] == [
        {"role": "user", "content": "Msg 1"},
        {"role": "assistant", "content": "Msg 2"},
        {"role": "user", "content": "Msg 3"},
    ]
