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

    storage.save_many.assert_awaited_once_with(turns)


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
