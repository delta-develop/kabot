import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel

from app.models.turn import Turn
from app.services.storage import relational_storage
from app.services.storage.relational_storage import RelationalStorage

INTEGRATION_DATABASE_URL = os.getenv("POSTGRES_INTEGRATION_URL")
pytestmark = pytest.mark.skipif(
    not INTEGRATION_DATABASE_URL,
    reason="POSTGRES_INTEGRATION_URL is not configured",
)


def turn(
    subject_id: str,
    session_id: str,
    seq: int,
    ts: datetime,
    embedding: list[float] | None = None,
) -> Turn:
    return Turn(
        subject_id=subject_id,
        session_id=session_id,
        seq=seq,
        ts=ts,
        user_text=f"user {seq}",
        assistant_text=f"assistant {seq}",
        embedding=embedding or [1.0] + [0.0] * 1535,
    )


@asynccontextmanager
async def integration_storage(monkeypatch):
    monkeypatch.setattr(relational_storage, "DATABASE_URL", INTEGRATION_DATABASE_URL)
    storage = RelationalStorage()
    await storage.setup()
    try:
        yield storage
    finally:
        assert storage.engine is not None
        await storage.engine.dispose()


async def delete_turns(storage: RelationalStorage, subject_id: str) -> None:
    table = SQLModel.metadata.tables["turn"]
    assert storage.engine is not None
    async with storage.engine.begin() as connection:
        await connection.execute(delete(table).where(table.c.subject_id == subject_id))


@pytest.mark.asyncio
async def test_turn_log_writes_vectors_orders_history_and_rejects_duplicate_seq(
    monkeypatch,
):
    token = uuid4().hex
    subject_id = f"subject-{token}"
    session_id = f"session-{token}"
    now = datetime.now(UTC)

    async with integration_storage(monkeypatch) as storage:
        try:
            turns = [
                turn(subject_id, session_id, 0, now),
                turn(subject_id, session_id, 1, now + timedelta(seconds=1)),
            ]
            await storage.save_many(turns)

            history = await storage.history(subject_id)

            assert [item.seq for item in history] == [0, 1]
            assert len(history[0].embedding) == 1536
            with pytest.raises(IntegrityError):
                await storage.save_many(
                    [turn(subject_id, session_id, 1, now + timedelta(seconds=2))]
                )
        finally:
            await delete_turns(storage, subject_id)


@pytest.mark.asyncio
async def test_associative_recall_returns_past_hit_neighbors_and_excludes_current_session(
    monkeypatch,
):
    token = uuid4().hex
    subject_id = f"subject-{token}"
    past_session_id = f"past-{token}"
    current_session_id = f"current-{token}"
    now = datetime.now(UTC)
    query = [1.0] + [0.0] * 1535
    unrelated_a = [0.0, 1.0] + [0.0] * 1534
    unrelated_b = [0.0, 0.0, 1.0] + [0.0] * 1533
    monkeypatch.setattr(relational_storage, "RECALL_WINDOW", 1)
    monkeypatch.setattr(relational_storage, "RECALL_MIN_SIMILARITY", -1.0)

    async with integration_storage(monkeypatch) as storage:
        try:
            await storage.save_many(
                [
                    turn(subject_id, past_session_id, 13, now, unrelated_a),
                    turn(
                        subject_id,
                        past_session_id,
                        14,
                        now + timedelta(seconds=1),
                        query,
                    ),
                    turn(
                        subject_id,
                        past_session_id,
                        15,
                        now + timedelta(seconds=2),
                        unrelated_b,
                    ),
                    turn(
                        subject_id,
                        current_session_id,
                        0,
                        now + timedelta(seconds=3),
                        query,
                    ),
                ]
            )

            assert await storage.has_turns(subject_id) is True
            assert await storage.has_turns(f"missing-{token}") is False
            fragments = await storage.similar(
                subject_id,
                query,
                k=1,
                exclude_session=current_session_id,
            )

            assert len(fragments) == 1
            assert fragments[0].session_id == past_session_id
            assert [item.seq for item in fragments[0].turns] == [13, 14, 15]
            assert all(item.subject_id == subject_id for item in fragments[0].turns)
            assert all(
                item.session_id != current_session_id for item in fragments[0].turns
            )
        finally:
            await delete_turns(storage, subject_id)


@pytest.mark.asyncio
async def test_has_turns_can_exclude_the_current_session(monkeypatch):
    subject_id = f"exclusion-{uuid4()}"
    base = datetime(2026, 1, 1, tzinfo=UTC)

    async with integration_storage(monkeypatch) as storage:
        try:
            await storage.save_many([turn(subject_id, "only-session", 0, base)])

            assert await storage.has_turns(subject_id) is True
            assert (
                await storage.has_turns(subject_id, exclude_session="only-session")
                is False
            )
            assert (
                await storage.has_turns(subject_id, exclude_session="other-session")
                is True
            )
        finally:
            await delete_turns(storage, subject_id)


@pytest.mark.asyncio
async def test_by_session_pages_in_sequence_order(monkeypatch):
    subject_id = f"paging-{uuid4()}"
    session_id = f"session-{uuid4()}"
    base = datetime(2026, 1, 1, tzinfo=UTC)

    async with integration_storage(monkeypatch) as storage:
        try:
            await storage.save_many(
                [
                    turn(subject_id, session_id, seq, base + timedelta(minutes=seq))
                    for seq in (2, 0, 1, 3)
                ]
            )

            first_page = await storage.by_session(session_id, limit=2)
            second_page = await storage.by_session(session_id, limit=2, offset=2)

            assert [item.seq for item in first_page] == [0, 1]
            assert [item.seq for item in second_page] == [2, 3]
        finally:
            await delete_turns(storage, subject_id)


@pytest.mark.asyncio
async def test_delete_removes_only_the_named_subject(monkeypatch):
    subject_id = f"erased-{uuid4()}"
    bystander_id = f"kept-{uuid4()}"
    base = datetime(2026, 1, 1, tzinfo=UTC)

    async with integration_storage(monkeypatch) as storage:
        try:
            await storage.save_many(
                [
                    turn(subject_id, "session-a", 0, base),
                    turn(bystander_id, "session-b", 0, base),
                ]
            )

            await storage.delete(subject_id)

            assert await storage.has_turns(subject_id) is False
            assert await storage.has_turns(bystander_id) is True
        finally:
            await delete_turns(storage, bystander_id)


@pytest.mark.asyncio
async def test_append_many_skips_turns_already_logged(monkeypatch):
    """A replayed session adds only what is missing; `save_many` still refuses."""
    token = uuid4().hex
    subject_id = f"subject-{token}"
    session_id = f"session-{token}"
    now = datetime.now(UTC)

    async with integration_storage(monkeypatch) as storage:
        try:
            first = [
                turn(subject_id, session_id, 0, now),
                turn(subject_id, session_id, 1, now + timedelta(seconds=1)),
            ]
            await storage.append_many(first)
            await storage.append_many(
                first + [turn(subject_id, session_id, 2, now + timedelta(seconds=2))]
            )

            history = await storage.history(subject_id)

            assert [item.seq for item in history] == [0, 1, 2]
            with pytest.raises(IntegrityError):
                await storage.save_many([turn(subject_id, session_id, 0, now)])
        finally:
            await delete_turns(storage, subject_id)
