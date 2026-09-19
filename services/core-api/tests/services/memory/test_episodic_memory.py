import pytest
from unittest.mock import AsyncMock, patch
from app.services.memory.episodic_memory import EpisodicMemory

@pytest.mark.asyncio
@patch("app.services.memory.episodic_memory.NonRelationalStorage")
async def test_store_in_memory(mock_storage_cls):
    mock_storage = AsyncMock()
    mock_storage_cls.return_value = mock_storage
    memory = EpisodicMemory()

    await memory.store_in_memory("123", [{"role": "user", "content": "hello"}])
    mock_storage.save.assert_awaited_once_with({"whatsapp_id": "123", "data": [{"role": "user", "content": "hello"}]})

@pytest.mark.asyncio
@patch("app.services.memory.episodic_memory.NonRelationalStorage")
async def test_retrieve_from_memory_found(mock_storage_cls):
    mock_storage = AsyncMock()
    mock_storage.get.return_value = {"history": ["msg1", "msg2"]}
    mock_storage_cls.return_value = mock_storage
    memory = EpisodicMemory()

    result = await memory.retrieve_from_memory("123")
    assert result == ["msg1", "msg2"]

@pytest.mark.asyncio
@patch("app.services.memory.episodic_memory.NonRelationalStorage")
async def test_retrieve_from_memory_not_found(mock_storage_cls):
    mock_storage = AsyncMock()
    mock_storage.get.return_value = None
    mock_storage_cls.return_value = mock_storage
    memory = EpisodicMemory()

    result = await memory.retrieve_from_memory("123")
    assert result == []

@pytest.mark.asyncio
@patch("app.services.memory.episodic_memory.NonRelationalStorage")
async def test_delete_from_memory(mock_storage_cls):
    mock_storage = AsyncMock()
    mock_storage_cls.return_value = mock_storage
    memory = EpisodicMemory()

    await memory.delete_from_memory("123")
    mock_storage.delete.assert_awaited_once_with("123")