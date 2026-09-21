from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.models.session import SessionDocument
from app.workers import consolidation


def session(status: str = "open") -> SessionDocument:
    return SessionDocument(
        subject_id="leo",
        turns=[],
        last_activity=datetime.now(UTC),
        status=status,
    )


@pytest.fixture
def stream(mocker):
    """Replaces the stream calls the worker makes, one mock per verb."""
    return {
        name: mocker.patch.object(consolidation, name, new=AsyncMock())
        for name in ("ack", "dead_letter", "claim_stale", "read_new", "enqueue")
    }


@pytest.mark.asyncio
async def test_a_successful_consolidation_is_acknowledged(stream):
    orchestrator = AsyncMock()
    working_memory = AsyncMock()
    working_memory.retrieve_from_memory.return_value = session()

    await consolidation.handle_message(
        orchestrator, working_memory, ("1-0", {"session_id": "session-a"}, 1)
    )

    orchestrator.persist_conversation_closure.assert_awaited_once_with(
        "leo", "session-a"
    )
    stream["ack"].assert_awaited_once_with("1-0")


@pytest.mark.asyncio
async def test_a_failed_attempt_with_retries_left_is_not_acknowledged(stream):
    orchestrator = AsyncMock()
    orchestrator.persist_conversation_closure.side_effect = RuntimeError("pg is down")
    working_memory = AsyncMock()
    working_memory.retrieve_from_memory.return_value = session()

    await consolidation.handle_message(
        orchestrator, working_memory, ("1-0", {"session_id": "session-a"}, 2)
    )

    stream["ack"].assert_not_awaited()
    stream["dead_letter"].assert_not_awaited()


@pytest.mark.asyncio
async def test_the_last_attempt_fails_the_session_and_dead_letters_the_message(stream):
    orchestrator = AsyncMock()
    orchestrator.persist_conversation_closure.side_effect = RuntimeError("pg is down")
    working_memory = AsyncMock()
    working_memory.retrieve_from_memory.return_value = session()
    fields = {"session_id": "session-a"}

    await consolidation.handle_message(
        orchestrator, working_memory, ("1-0", fields, consolidation.MAX_RETRIES)
    )

    stream["dead_letter"].assert_awaited_once()
    assert stream["dead_letter"].await_args.args[0] == fields
    assert "pg is down" in stream["dead_letter"].await_args.args[1]
    assert working_memory.store_in_memory.await_args.args[1].status == "failed"
    stream["ack"].assert_awaited_once_with("1-0")


@pytest.mark.asyncio
async def test_an_already_consolidated_session_is_not_consolidated_again(stream):
    orchestrator = AsyncMock()
    working_memory = AsyncMock()
    working_memory.retrieve_from_memory.return_value = session("consolidated")

    await consolidation.handle_message(
        orchestrator, working_memory, ("1-0", {"session_id": "session-a"}, 1)
    )

    orchestrator.persist_conversation_closure.assert_not_awaited()
    stream["ack"].assert_awaited_once_with("1-0")


@pytest.mark.asyncio
async def test_a_vanished_session_leaves_the_open_index(stream):
    orchestrator = AsyncMock()
    working_memory = AsyncMock()
    working_memory.retrieve_from_memory.return_value = None

    await consolidation.handle_message(
        orchestrator, working_memory, ("1-0", {"session_id": "session-a"}, 1)
    )

    working_memory.drop_from_open.assert_awaited_once_with("session-a")
    orchestrator.persist_conversation_closure.assert_not_awaited()
    stream["ack"].assert_awaited_once_with("1-0")


@pytest.mark.asyncio
async def test_an_open_session_is_marked_consolidating_before_the_work(stream):
    orchestrator = AsyncMock()
    working_memory = AsyncMock()
    working_memory.retrieve_from_memory.return_value = session()

    await consolidation.consolidate_session(orchestrator, working_memory, "session-a")

    assert working_memory.store_in_memory.await_args.args[1].status == "consolidating"


@pytest.mark.asyncio
async def test_the_sweep_queues_sessions_idle_one_margin_before_the_ttl(stream):
    working_memory = AsyncMock()
    working_memory.open_sessions_before.return_value = ["session-a", "session-b"]

    queued = await consolidation.sweep_once(working_memory)

    cutoff = working_memory.open_sessions_before.await_args.args[0]
    expected = datetime.now(UTC) - timedelta(
        seconds=consolidation.SESSION_TTL_SECONDS - consolidation.SWEEP_MARGIN_SECONDS
    )
    assert abs((cutoff - expected).total_seconds()) < 1
    assert queued == ["session-a", "session-b"]
    assert [call.args[0] for call in stream["enqueue"].await_args_list] == [
        "session-a",
        "session-b",
    ]


@pytest.mark.asyncio
async def test_messages_left_by_a_dead_worker_come_before_new_ones(stream):
    orchestrator = AsyncMock()
    working_memory = AsyncMock()
    working_memory.retrieve_from_memory.return_value = session()
    stream["claim_stale"].return_value = [("1-0", {"session_id": "stale"}, 2)]

    handled = await consolidation.consume_once(orchestrator, working_memory, "worker-1")

    assert handled == 1
    stream["read_new"].assert_not_awaited()
    orchestrator.persist_conversation_closure.assert_awaited_once_with("leo", "stale")
