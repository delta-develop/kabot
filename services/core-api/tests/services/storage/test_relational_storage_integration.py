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

            assert [item.seq for item in history] == [1, 0]
            assert len(history[0].embedding) == 1536
            with pytest.raises(IntegrityError):
                await storage.save_many(
                    [turn(subject_id, session_id, 1, now + timedelta(seconds=2))]
                )
        finally:
            await delete_turns(storage, subject_id)


@pytest.mark.asyncio
async def test_knn_orders_turns_and_isolates_subject(monkeypatch):
    token = uuid4().hex
    subject_id = f"subject-{token}"
    other_subject_id = f"other-{token}"
    now = datetime.now(UTC)
    near = [1.0] + [0.0] * 1535
    far = [0.0, 1.0] + [0.0] * 1534

    async with integration_storage(monkeypatch) as storage:
        try:
            await storage.save_many(
                [
                    turn(subject_id, f"session-{token}", 0, now, near),
                    turn(subject_id, f"session-{token}", 1, now, far),
                    turn(other_subject_id, f"other-session-{token}", 0, now, near),
                ]
            )

            results = await storage.knn_search(subject_id, near, k=10)

            assert [row["seq"] for row in results] == [0, 1]
            assert all(row["subject_id"] == subject_id for row in results)
            assert all("embedding" not in row for row in results)
        finally:
            await delete_turns(storage, subject_id)
            await delete_turns(storage, other_subject_id)
