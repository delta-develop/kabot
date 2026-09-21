import os
from typing import Any

from sqlalchemy import and_
from sqlalchemy import delete as sql_delete
from sqlalchemy import exists, text, tuple_
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel, select

from app.models.turn import Fragment, Turn
from app.services.storage.base import Storage

DATABASE_URL = os.getenv(
    "DB_ASYNC_CONNECTION_STR",
    "postgresql+asyncpg://elephant:elephant123@postgres:5432/elephant",
)
RECALL_MIN_SIMILARITY = float(os.getenv("RECALL_MIN_SIMILARITY", "-1.0"))
RECALL_WINDOW = int(os.getenv("RECALL_WINDOW", "1"))

engine: AsyncEngine | None = None
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


class RelationalStorage(Storage):
    def __init__(self) -> None:
        self.engine = engine
        self.session_local = AsyncSessionLocal

    async def setup(self) -> None:
        global engine, AsyncSessionLocal

        bootstrap_engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        try:
            async with bootstrap_engine.begin() as connection:
                await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        finally:
            await bootstrap_engine.dispose()

        engine = create_async_engine(DATABASE_URL)
        AsyncSessionLocal = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self.engine = engine
        self.session_local = AsyncSessionLocal

        async with engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)

    def _sessions(self) -> async_sessionmaker[AsyncSession]:
        if self.session_local is None:
            raise RuntimeError("Relational storage is not initialized")
        return self.session_local

    async def save(self, data: dict[str, Any]) -> None:
        await self.save_many([Turn(**data)])

    async def save_many(self, turns: list[Turn]) -> None:
        async with self._sessions()() as session:
            async with session.begin():
                session.add_all(turns)

    async def get(self, filters: dict[str, Any]) -> list[Turn]:
        async with self._sessions()() as session:
            statement = select(Turn)
            for key, value in filters.items():
                statement = statement.where(getattr(Turn, key) == value)
            result = await session.execute(statement)
            return list(result.scalars().all())

    async def history(self, subject_id: str, limit: int | None = None) -> list[Turn]:
        columns = SQLModel.metadata.tables["turn"].c
        if limit is None:
            statement = select(Turn).where(columns.subject_id == subject_id)
        else:
            latest_ids = (
                select(columns.id)
                .where(columns.subject_id == subject_id)
                .order_by(
                    columns.ts.desc(), columns.session_id.desc(), columns.seq.desc()
                )
                .limit(limit)
            )
            statement = select(Turn).where(columns.id.in_(latest_ids))
        statement = statement.order_by(
            columns.ts.asc(), columns.session_id.asc(), columns.seq.asc()
        )
        async with self._sessions()() as session:
            result = await session.execute(statement)
            return list(result.scalars().all())

    async def has_turns(
        self, subject_id: str, exclude_session: str | None = None
    ) -> bool:
        columns = SQLModel.metadata.tables["turn"].c
        condition = columns.subject_id == subject_id
        if exclude_session is not None:
            condition = and_(condition, columns.session_id != exclude_session)
        statement = select(exists().where(condition))
        async with self._sessions()() as session:
            result = await session.execute(statement)
            return bool(result.scalar())

    async def by_session(
        self, session_id: str, limit: int, offset: int = 0
    ) -> list[Turn]:
        columns = SQLModel.metadata.tables["turn"].c
        statement = (
            select(Turn)
            .where(columns.session_id == session_id)
            .order_by(columns.seq.asc())
            .limit(limit)
            .offset(offset)
        )
        async with self._sessions()() as session:
            result = await session.execute(statement)
            return list(result.scalars().all())

    async def delete(self, subject_id: str) -> None:
        columns = SQLModel.metadata.tables["turn"].c
        async with self._sessions()() as session:
            async with session.begin():
                await session.execute(
                    sql_delete(Turn).where(columns.subject_id == subject_id)
                )

    async def similar(
        self,
        subject_id: str,
        vector: list[float],
        k: int,
        exclude_session: str | None = None,
    ) -> list[Fragment]:
        if not isinstance(k, int) or not 1 <= k <= 100:
            raise ValueError("k must be between 1 and 100")
        if RECALL_WINDOW < 0:
            raise ValueError("RECALL_WINDOW must be zero or greater")

        columns = SQLModel.metadata.tables["turn"].c
        distance = columns.embedding.cosine_distance(vector).label("distance")
        statement = (
            select(columns.session_id, columns.seq, distance)
            .where(columns.subject_id == subject_id)
            .order_by(distance.asc())
            .limit(k)
        )
        if exclude_session is not None:
            statement = statement.where(columns.session_id != exclude_session)

        async with self._sessions()() as session:
            async with session.begin():
                # The subject filter can otherwise exhaust HNSW candidates early.
                await session.execute(
                    text("SET LOCAL hnsw.iterative_scan = relaxed_order")
                )
                result = await session.execute(statement)
                hits = [
                    {
                        "session_id": row["session_id"],
                        "seq": row["seq"],
                        "similarity": 1 - float(row["distance"]),
                    }
                    for row in result.mappings().all()
                    if 1 - float(row["distance"]) >= RECALL_MIN_SIMILARITY
                ]
                if not hits:
                    return []

                windows: list[dict[str, Any]] = []
                for hit in sorted(
                    hits, key=lambda item: (item["session_id"], item["seq"])
                ):
                    start = hit["seq"] - RECALL_WINDOW
                    end = hit["seq"] + RECALL_WINDOW
                    if (
                        windows
                        and windows[-1]["session_id"] == hit["session_id"]
                        and start <= windows[-1]["end"]
                    ):
                        windows[-1]["end"] = max(windows[-1]["end"], end)
                        windows[-1]["similarity"] = max(
                            windows[-1]["similarity"], hit["similarity"]
                        )
                    else:
                        windows.append(
                            {
                                "session_id": hit["session_id"],
                                "start": start,
                                "end": end,
                                "similarity": hit["similarity"],
                            }
                        )

                pairs = [
                    (window["session_id"], seq)
                    for window in windows
                    for seq in range(window["start"], window["end"] + 1)
                ]
                neighbors = await session.execute(
                    select(Turn).where(
                        columns.subject_id == subject_id,
                        tuple_(columns.session_id, columns.seq).in_(pairs),
                    )
                )

        turns_by_session: dict[str, list[Turn]] = {}
        for turn in neighbors.scalars().all():
            turns_by_session.setdefault(turn.session_id, []).append(turn)

        fragments = []
        for window in windows:
            turns = sorted(
                (
                    turn
                    for turn in turns_by_session[window["session_id"]]
                    if window["start"] <= turn.seq <= window["end"]
                ),
                key=lambda turn: turn.seq,
            )
            fragments.append(
                Fragment(
                    turns=turns,
                    session_id=window["session_id"],
                    ts=turns[0].ts,
                    similarity=window["similarity"],
                )
            )
        return sorted(
            fragments,
            key=lambda fragment: (
                -fragment.similarity,
                fragment.ts,
                fragment.session_id,
                fragment.turns[0].seq,
            ),
        )
