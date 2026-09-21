"""The three failure modes this worker exists to survive, against real backends.

Mocks cannot show that a retry does not duplicate: the guarantee lives in a
Postgres constraint and in Redis pending entries, so these run against both.
"""

import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlmodel import SQLModel

from app.models.session import SessionDocument, TurnDraft
from app.services.memory import cognitive_orchestrator as orchestrator_module
from app.services.memory.cognitive_orchestrator import CognitiveOrchestrator
from app.services.memory.episodic_memory import EpisodicMemory
from app.services.memory.working_memory import OPEN_SESSIONS_KEY, WorkingMemory
from app.services.storage import connections, consolidation_stream, relational_storage
from app.services.storage.relational_storage import RelationalStorage
from app.workers import consolidation

INTEGRATION_DATABASE_URL = os.getenv("POSTGRES_INTEGRATION_URL")

pytestmark = pytest.mark.skipif(
    not (INTEGRATION_DATABASE_URL and os.getenv("REDIS_URL")),
    reason="POSTGRES_INTEGRATION_URL and REDIS_URL are not both configured",
)

EMBEDDING = [1.0] + [0.0] * 1535


@pytest.fixture
def fresh_redis():
    """Rebind the Redis singleton to this test's event loop."""
    connections._redis_client = None
    yield
    connections._redis_client = None


def conversation(subject_id: str) -> SessionDocument:
    now = datetime.now(UTC)
    return SessionDocument(
        subject_id=subject_id,
        turns=[
            TurnDraft(
                seq=index,
                ts=now + timedelta(seconds=index),
                user_text=f"user {index}",
                assistant_text=f"assistant {index}",
            )
            for index in range(2)
        ],
        last_activity=now,
    )


def isolate_stream(monkeypatch, token: str) -> None:
    """Gives the test its own stream, group and failed stream."""
    monkeypatch.setattr(consolidation_stream, "STREAM", f"consolidation-{token}")
    monkeypatch.setattr(consolidation_stream, "GROUP", f"consolidators-{token}")
    monkeypatch.setattr(
        consolidation_stream, "FAILED_STREAM", f"consolidation-{token}:failed"
    )
    monkeypatch.setattr(consolidation_stream, "CLAIM_IDLE_MS", 0)


@asynccontextmanager
async def worker(monkeypatch):
    """Real working and episodic memory; summary, facts and the LLM mocked."""
    monkeypatch.setattr(relational_storage, "DATABASE_URL", INTEGRATION_DATABASE_URL)
    storage = RelationalStorage()
    await storage.setup()
    monkeypatch.setattr(
        orchestrator_module,
        "get_embeddings",
        AsyncMock(side_effect=lambda texts: [EMBEDDING for _ in texts]),
    )

    orchestrator = CognitiveOrchestrator()
    orchestrator.llm = AsyncMock()
    orchestrator.working_memory = WorkingMemory()
    orchestrator.episodic_memory = EpisodicMemory()
    orchestrator.summary_memory = AsyncMock()
    orchestrator.fact_memory = AsyncMock()
    try:
        yield orchestrator, WorkingMemory()
    finally:
        assert storage.engine is not None
        await storage.engine.dispose()


async def erase(subject_id: str, session_id: str, token: str) -> None:
    redis = await connections.get_redis_client()
    await redis.delete(
        f"session:{session_id}",
        f"consolidation-{token}",
        f"consolidation-{token}:failed",
    )
    await redis.zrem(OPEN_SESSIONS_KEY, session_id)
    table = SQLModel.metadata.tables["turn"]
    engine = relational_storage.engine
    assert engine is not None
    async with engine.begin() as connection:
        await connection.execute(delete(table).where(table.c.subject_id == subject_id))


async def pending_count() -> int:
    redis = await connections.get_redis_client()
    summary = await redis.xpending(
        consolidation_stream.STREAM, consolidation_stream.GROUP
    )
    return int(summary["pending"])


async def take(session_id: str, consumer: str, claimed: bool):
    """Returns this session's message, ignoring anything else in the stream."""
    reader = consolidation_stream.claim_stale if claimed else None
    messages = (
        await reader(consumer, 10)
        if reader
        else await consolidation_stream.read_new(consumer, 10, 50)
    )
    return next(
        message for message in messages if message[1]["session_id"] == session_id
    )


@pytest.mark.asyncio
async def test_a_worker_that_dies_before_the_ack_does_not_duplicate_turns(
    monkeypatch, fresh_redis
):
    token = uuid4().hex
    subject_id, session_id = f"subject-{token}", f"session-{token}"
    isolate_stream(monkeypatch, token)

    async with worker(monkeypatch) as (orchestrator, working_memory):
        try:
            await working_memory.store_in_memory(session_id, conversation(subject_id))
            await consolidation_stream.ensure_group()
            await consolidation_stream.enqueue(session_id)

            # Death is simulated where it hurts: the turns are already in
            # Postgres and the message is not acknowledged yet.
            orchestrator.summary_memory.store_in_memory.side_effect = RuntimeError(
                "worker killed"
            )
            await consolidation.handle_message(
                orchestrator, working_memory, await take(session_id, "worker-1", False)
            )

            assert len(await EpisodicMemory().by_session(session_id, 50)) == 2
            assert await pending_count() == 1

            orchestrator.summary_memory.store_in_memory.side_effect = None
            claimed = await take(session_id, "worker-2", True)
            assert claimed[2] == 2
            await consolidation.handle_message(orchestrator, working_memory, claimed)

            turns = await EpisodicMemory().by_session(session_id, 50)
            assert [turn.seq for turn in turns] == [0, 1]
            assert await pending_count() == 0
            stored = await working_memory.retrieve_from_memory(session_id)
            assert stored is not None
            assert stored.status == "consolidated"
            assert stored.turns == []
        finally:
            await erase(subject_id, session_id, token)


@pytest.mark.asyncio
async def test_three_failures_fail_the_session_and_move_the_message_aside(
    monkeypatch, fresh_redis
):
    token = uuid4().hex
    subject_id, session_id = f"subject-{token}", f"session-{token}"
    isolate_stream(monkeypatch, token)

    async with worker(monkeypatch) as (orchestrator, working_memory):
        try:
            await working_memory.store_in_memory(session_id, conversation(subject_id))
            await consolidation_stream.ensure_group()
            await consolidation_stream.enqueue(session_id)
            orchestrator.summary_memory.store_in_memory.side_effect = RuntimeError(
                "mongo is down"
            )

            await consolidation.handle_message(
                orchestrator, working_memory, await take(session_id, "worker-1", False)
            )
            for attempt in range(2, consolidation.MAX_RETRIES + 1):
                message = await take(session_id, f"worker-{attempt}", True)
                assert message[2] == attempt
                await consolidation.handle_message(
                    orchestrator, working_memory, message
                )

            stored = await working_memory.retrieve_from_memory(session_id)
            assert stored is not None
            assert stored.status == "failed"
            assert await pending_count() == 0

            redis = await connections.get_redis_client()
            failed = await redis.xrange(consolidation_stream.FAILED_STREAM)
            assert len(failed) == 1
            assert failed[0][1]["session_id"] == session_id
            assert "mongo is down" in failed[0][1]["error"]
            assert await redis.zscore(OPEN_SESSIONS_KEY, session_id) is None
        finally:
            await erase(subject_id, session_id, token)


@pytest.mark.asyncio
async def test_an_abandoned_session_is_swept_queued_and_consolidated(
    monkeypatch, fresh_redis
):
    token = uuid4().hex
    subject_id, session_id = f"subject-{token}", f"session-{token}"
    isolate_stream(monkeypatch, token)

    async with worker(monkeypatch) as (orchestrator, working_memory):
        try:
            await working_memory.store_in_memory(session_id, conversation(subject_id))
            await consolidation_stream.ensure_group()
            redis = await connections.get_redis_client()
            assert await redis.zscore(OPEN_SESSIONS_KEY, session_id) is not None

            idle_since = datetime.now(UTC) - timedelta(
                seconds=consolidation.SESSION_TTL_SECONDS
                - consolidation.SWEEP_MARGIN_SECONDS
                + 60
            )
            await redis.zadd(OPEN_SESSIONS_KEY, {session_id: idle_since.timestamp()})

            assert session_id in await consolidation.sweep_once(working_memory)

            await consolidation.handle_message(
                orchestrator, working_memory, await take(session_id, "worker-1", False)
            )

            stored = await working_memory.retrieve_from_memory(session_id)
            assert stored is not None
            assert stored.status == "consolidated"
            assert len(await EpisodicMemory().by_session(session_id, 50)) == 2
            assert await redis.zscore(OPEN_SESSIONS_KEY, session_id) is None
        finally:
            await erase(subject_id, session_id, token)
