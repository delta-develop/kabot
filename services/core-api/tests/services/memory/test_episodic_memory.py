from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.models.session import TurnDraft
from app.services.memory.episodic_memory import EpisodicMemory


def stored_turn() -> dict:
    return {
        "session_id": "session-id",
        "seq": 0,
        "ts": datetime.now(UTC).isoformat(),
        "user_text": "hello",
        "assistant_text": "hi",
    }


@pytest.mark.asyncio
@patch("app.services.memory.episodic_memory.NonRelationalStorage")
async def test_store_in_memory_uses_subject_id(mock_storage_cls):
    mock_storage = AsyncMock()
    mock_storage_cls.return_value = mock_storage
    memory = EpisodicMemory()
    turns = [stored_turn()]

    await memory.store_in_memory("leo", turns)

    mock_storage.save.assert_awaited_once_with({"subject_id": "leo", "data": turns})


@pytest.mark.asyncio
@patch("app.services.memory.episodic_memory.NonRelationalStorage")
async def test_retrieve_from_memory_returns_turn_drafts(mock_storage_cls):
    mock_storage = AsyncMock()
    stored = stored_turn()
    mock_storage.get.return_value = {"history": [stored]}
    mock_storage_cls.return_value = mock_storage
    memory = EpisodicMemory()

    result = await memory.retrieve_from_memory("leo")

    assert result == [TurnDraft.model_validate(stored)]
    mock_storage.get.assert_awaited_once_with({"subject_id": "leo"})


@pytest.mark.asyncio
@patch("app.services.memory.episodic_memory.NonRelationalStorage")
async def test_retrieve_from_memory_not_found(mock_storage_cls):
    mock_storage = AsyncMock()
    mock_storage.get.return_value = None
    mock_storage_cls.return_value = mock_storage

    assert await EpisodicMemory().retrieve_from_memory("leo") == []


@pytest.mark.asyncio
@patch("app.services.memory.episodic_memory.NonRelationalStorage")
async def test_delete_from_memory(mock_storage_cls):
    mock_storage = AsyncMock()
    mock_storage_cls.return_value = mock_storage

    await EpisodicMemory().delete_from_memory("leo")

    mock_storage.delete.assert_awaited_once_with("leo")
