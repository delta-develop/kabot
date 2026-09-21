from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.models.turn import Turn
from app.services.memory.episodic_memory import EpisodicMemory


def turn(seq: int = 0) -> Turn:
    return Turn(
        subject_id="leo",
        session_id="session-id",
        seq=seq,
        ts=datetime.now(UTC),
        user_text="hello",
        assistant_text="hi",
        embedding=[0.0] * 1536,
    )


@pytest.mark.asyncio
@patch("app.services.memory.episodic_memory.RelationalStorage")
async def test_append_writes_turns(mock_storage_cls):
    storage = AsyncMock()
    mock_storage_cls.return_value = storage
    turns = [turn()]

    await EpisodicMemory().append(turns)

    storage.append_many.assert_awaited_once_with(turns)


@pytest.mark.asyncio
@patch("app.services.memory.episodic_memory.RelationalStorage")
async def test_history_returns_subject_turns(mock_storage_cls):
    storage = AsyncMock()
    turns = [turn(1), turn(0)]
    storage.history.return_value = turns
    mock_storage_cls.return_value = storage

    result = await EpisodicMemory().history("leo", limit=2)

    assert result == turns
    storage.history.assert_awaited_once_with("leo", 2)


@pytest.mark.asyncio
@patch("app.services.memory.episodic_memory.RelationalStorage")
async def test_has_turns_delegates_to_storage(mock_storage_cls):
    storage = AsyncMock()
    storage.has_turns.return_value = True
    mock_storage_cls.return_value = storage

    assert await EpisodicMemory().has_turns("leo") is True
    storage.has_turns.assert_awaited_once_with("leo", None)


@pytest.mark.asyncio
@patch("app.services.memory.episodic_memory.RelationalStorage")
async def test_has_turns_forwards_the_session_exclusion(mock_storage_cls):
    storage = AsyncMock()
    storage.has_turns.return_value = False
    mock_storage_cls.return_value = storage

    result = await EpisodicMemory().has_turns("leo", exclude_session="current")

    assert result is False
    storage.has_turns.assert_awaited_once_with("leo", "current")


@pytest.mark.asyncio
@patch("app.services.memory.episodic_memory.RelationalStorage")
async def test_by_session_delegates_to_storage(mock_storage_cls):
    storage = AsyncMock()
    storage.by_session.return_value = []
    mock_storage_cls.return_value = storage

    assert await EpisodicMemory().by_session("session-id", 10, 5) == []
    storage.by_session.assert_awaited_once_with("session-id", 10, 5)


@pytest.mark.asyncio
@patch("app.services.memory.episodic_memory.RelationalStorage")
async def test_delete_delegates_to_storage(mock_storage_cls):
    storage = AsyncMock()
    mock_storage_cls.return_value = storage

    await EpisodicMemory().delete("leo")

    storage.delete.assert_awaited_once_with("leo")


@pytest.mark.asyncio
@patch("app.services.memory.episodic_memory.RelationalStorage")
async def test_similar_delegates_to_storage(mock_storage_cls):
    storage = AsyncMock()
    storage.similar.return_value = []
    mock_storage_cls.return_value = storage
    vector = [0.0] * 1536

    result = await EpisodicMemory().similar("leo", vector, 5, exclude_session="current")

    assert result == []
    storage.similar.assert_awaited_once_with("leo", vector, 5, "current")
