import pytest
from unittest.mock import AsyncMock, patch
from app.services.memory.working_memory import WorkingMemory


@pytest.mark.asyncio
async def test_store_in_memory_appends_to_existing_list():
    memory = WorkingMemory()
    memory.storage = AsyncMock()
    memory.storage.get.return_value = ["existing"]
    await memory.store_in_memory("test_key", ["new_item"])
    memory.storage.set.assert_awaited_with("test_key", ["existing", "new_item"])


@pytest.mark.asyncio
async def test_store_in_memory_appends_list():
    memory = WorkingMemory()
    memory.storage = AsyncMock()
    memory.storage.get.return_value = ["existing"]
    await memory.store_in_memory("test_key", ["new1", "new2"])
    memory.storage.set.assert_awaited_with("test_key", ["existing", "new1", "new2"])


@pytest.mark.asyncio
async def test_store_in_memory_raises_error_on_string():
    memory = WorkingMemory()
    with pytest.raises(ValueError):
        await memory.store_in_memory("test_key", "invalid string")


@pytest.mark.asyncio
async def test_retrieve_from_memory_returns_deserialized_json():
    memory = WorkingMemory()
    memory.storage = AsyncMock()
    memory.storage.get.return_value = '{"a": 1}'
    result = await memory.retrieve_from_memory("test_key")
    assert result == {"a": 1}


@pytest.mark.asyncio
async def test_retrieve_from_memory_returns_list_directly():
    memory = WorkingMemory()
    memory.storage = AsyncMock()
    memory.storage.get.return_value = [1, 2, 3]
    result = await memory.retrieve_from_memory("test_key")
    assert result == [1, 2, 3]


@pytest.mark.asyncio
async def test_retrieve_from_memory_returns_none():
    memory = WorkingMemory()
    memory.storage = AsyncMock()
    memory.storage.get.return_value = None
    result = await memory.retrieve_from_memory("test_key")
    assert result is None


@pytest.mark.asyncio
async def test_delete_from_memory():
    memory = WorkingMemory()
    memory.storage = AsyncMock()
    await memory.delete_from_memory("test_key")
    memory.storage.delete.assert_awaited_with("test_key")