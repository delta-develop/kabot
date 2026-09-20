import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.session import SessionDocument, TurnDraft
from app.services.memory.working_memory import WorkingMemory


def session_document() -> SessionDocument:
    return SessionDocument(
        subject_id="leo",
        turns=[
            TurnDraft(
                seq=0,
                ts=datetime.now(UTC),
                user_text="Hello",
                assistant_text="Hi",
            )
        ],
        last_activity=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_store_in_memory_serializes_session_with_ttl(mocker):
    memory = WorkingMemory()
    memory.storage = mocker.AsyncMock()
    session = session_document()

    await memory.store_in_memory("session-id", session)

    memory.storage.set.assert_awaited_once_with(
        "session-id", session.model_dump(mode="json"), ttl=1800
    )


@pytest.mark.asyncio
async def test_retrieve_from_memory_validates_session_document(mocker):
    memory = WorkingMemory()
    memory.storage = mocker.AsyncMock()
    session = session_document()
    memory.storage.get.return_value = session.model_dump(mode="json")

    result = await memory.retrieve_from_memory("session-id")

    assert result == session


@pytest.mark.asyncio
async def test_retrieve_from_memory_returns_none(mocker):
    memory = WorkingMemory()
    memory.storage = mocker.AsyncMock()
    memory.storage.get.return_value = None

    assert await memory.retrieve_from_memory("session-id") is None


@pytest.mark.asyncio
async def test_delete_from_memory(mocker):
    memory = WorkingMemory()
    memory.storage = mocker.AsyncMock()

    await memory.delete_from_memory("session-id")

    memory.storage.delete.assert_awaited_once_with("session-id")


def test_working_memory_uses_session_namespace():
    assert WorkingMemory().storage._make_key("id") == "session:id"


@pytest.mark.skipif(not os.getenv("REDIS_URL"), reason="REDIS_URL is not configured")
@pytest.mark.asyncio
async def test_real_redis_key_has_renewing_ttl():
    memory = WorkingMemory()
    session_id = str(uuid4())
    session = session_document()
    redis = await memory.storage._get_redis()

    try:
        await memory.store_in_memory(session_id, session)
        first_ttl = await redis.ttl(f"session:{session_id}")
        assert 0 < first_ttl <= 1800
        assert not await redis.exists(f"memory:{session_id}")

        await asyncio.sleep(1.1)
        await memory.store_in_memory(session_id, session)
        renewed_ttl = await redis.ttl(f"session:{session_id}")

        assert renewed_ttl > first_ttl - 1
    finally:
        await memory.delete_from_memory(session_id)
