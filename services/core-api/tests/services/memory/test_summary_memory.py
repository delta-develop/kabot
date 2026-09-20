from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.models.session import TurnDraft
from app.services.memory.summary_memory import SummaryMemory


@pytest.mark.asyncio
@patch("app.services.memory.summary_memory.NonRelationalStorage")
@patch("app.services.memory.summary_memory.LLMBase")
async def test_store_in_memory(mock_llm_class, mock_storage_class):
    mock_llm = AsyncMock()
    mock_llm.generate_response.return_value = ["merged summary"]
    mock_llm_class.return_value = mock_llm

    mock_storage = AsyncMock()
    mock_storage.get.return_value = {"summary": "old summary"}
    mock_storage_class.return_value = mock_storage

    memory = SummaryMemory(mock_llm)
    recent_turns = [
        TurnDraft(
            seq=0,
            ts=datetime.now(UTC),
            user_text="Hi",
            assistant_text="Hello",
        )
    ]
    await memory.store_in_memory("subject-123", recent_turns)

    mock_llm.generate_response.assert_awaited_once()
    prompt = mock_llm.generate_response.call_args.args[0][0]["content"]
    assert "user: Hi" in prompt
    assert "assistant: Hello" in prompt
    saved = mock_storage.save.await_args.args[0]
    assert saved["subject_id"] == "subject-123"
    assert saved["summary"] == ["merged summary"]
    assert saved["last_updated"]


@pytest.mark.asyncio
@patch("app.services.memory.summary_memory.NonRelationalStorage")
async def test_retrieve_from_memory(mock_storage_class):
    mock_storage = AsyncMock()
    mock_storage.get.return_value = {"summary": "This is a summary"}
    mock_storage_class.return_value = mock_storage

    memory = SummaryMemory(AsyncMock())
    result = await memory.retrieve_from_memory("subject-123")

    assert result == "This is a summary"


@pytest.mark.asyncio
@patch("app.services.memory.summary_memory.NonRelationalStorage")
async def test_delete_from_memory(mock_storage_class):
    mock_storage = AsyncMock()
    mock_storage_class.return_value = mock_storage

    memory = SummaryMemory(AsyncMock())
    await memory.delete_from_memory("subject-123")

    mock_storage.delete.assert_awaited_once_with("subject-123")
