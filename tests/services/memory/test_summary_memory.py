import pytest
from unittest.mock import AsyncMock, patch
from app.services.memory.summary_memory import SummaryMemory


@pytest.mark.asyncio
@patch("app.services.memory.summary_memory.NonRelationalStorage")
@patch("app.services.memory.summary_memory.LLMBase")
@patch("app.services.memory.summary_memory.build_summary_merge_prompt")
async def test_store_in_memory(mock_build_prompt, mock_llm_class, mock_storage_class):
    mock_llm = AsyncMock()
    mock_llm.generate_response.return_value = ["merged summary"]
    mock_llm_class.return_value = mock_llm

    mock_storage = AsyncMock()
    mock_storage.get.return_value = {"summary": "old summary"}
    mock_storage_class.return_value = mock_storage

    mock_build_prompt.return_value = "generated prompt"

    memory = SummaryMemory(mock_llm)
    await memory.store_in_memory("user123", [{"role": "user", "content": "Hi"}])

    mock_build_prompt.assert_called_once_with(recent_messages=[{"role": "user", "content": "Hi"}], previous_summary="old summary")
    mock_llm.generate_response.assert_awaited_once_with(["generated prompt"])
    mock_storage.save.assert_awaited_once_with({"whatsapp_id": "user123", "data": ["merged summary"]})


@pytest.mark.asyncio
@patch("app.services.memory.summary_memory.NonRelationalStorage")
async def test_retrieve_from_memory(mock_storage_class):
    mock_storage = AsyncMock()
    mock_storage.get.return_value = {"summary": "This is a summary"}
    mock_storage_class.return_value = mock_storage

    memory = SummaryMemory(AsyncMock())
    result = await memory.retrieve_from_memory("user123")

    assert result == "This is a summary"


@pytest.mark.asyncio
@patch("app.services.memory.summary_memory.NonRelationalStorage")
async def test_delete_from_memory(mock_storage_class):
    mock_storage = AsyncMock()
    mock_storage_class.return_value = mock_storage

    memory = SummaryMemory(AsyncMock())
    await memory.delete_from_memory("user123")

    mock_storage.delete.assert_awaited_once_with("user123")