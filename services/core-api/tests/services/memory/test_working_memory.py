import asyncio
import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models.session import SessionDocument, TurnDraft
from app.services.memory.working_memory import WorkingMemory
from app.services.storage import connections


@pytest.fixture
def fresh_redis():
    """Rebind the Redis singleton to this test's event loop.

    connections._redis_client is created once per process, so the second test
    that touches real Redis inherits a client bound to a loop that is already
    closed.
    """
    connections._redis_client = None
    yield
    connections._redis_client = None


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
async def test_real_redis_key_has_renewing_ttl(fresh_redis):
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


@pytest.mark.asyncio
async def test_track_session_indexes_the_session_under_its_subject(mocker):
    memory = WorkingMemory()
    index = mocker.patch.object(memory, "subject_index", new=AsyncMock())

    await memory.track_session("leo", "session-id")

    index.add_to_set.assert_awaited_once_with("leo", "session-id")


@pytest.mark.asyncio
async def test_forget_subject_deletes_every_indexed_session_and_the_index(mocker):
    memory = WorkingMemory()
    index = mocker.patch.object(memory, "subject_index", new=AsyncMock())
    index.members.return_value = ["session-a", "session-b"]
    storage = mocker.patch.object(memory, "storage", new=AsyncMock())

    await memory.forget_subject("leo")

    assert [call.args[0] for call in storage.delete.await_args_list] == [
        "session-a",
        "session-b",
    ]
    index.delete.assert_awaited_once_with("leo")


@pytest.mark.skipif(not os.getenv("REDIS_URL"), reason="REDIS_URL is not configured")
@pytest.mark.asyncio
async def test_real_redis_forgets_a_subject_across_every_indexed_session(fresh_redis):
    memory = WorkingMemory()
    subject_id = f"subject-{uuid4()}"
    session_ids = [str(uuid4()), str(uuid4())]
    redis = await memory.storage._get_redis()

    try:
        for session_id in session_ids:
            await memory.store_in_memory(session_id, session_document())
            await memory.track_session(subject_id, session_id)

        assert sorted(await memory.session_ids(subject_id)) == sorted(session_ids)

        await memory.forget_subject(subject_id)

        for session_id in session_ids:
            assert not await redis.exists(f"session:{session_id}")
        assert not await redis.exists(f"subject_sessions:{subject_id}")
        assert await memory.session_ids(subject_id) == []
    finally:
        for session_id in session_ids:
            await memory.delete_from_memory(session_id)
        await memory.subject_index.delete(subject_id)
