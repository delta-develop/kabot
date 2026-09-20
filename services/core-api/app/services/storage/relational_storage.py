import os
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel, select

from app.models.turn import Turn
from app.services.storage.base import Storage

DATABASE_URL = os.getenv(
    "DB_ASYNC_CONNECTION_STR",
    "postgresql+asyncpg://elephant:elephant123@postgres:5432/elephant",
)

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

    async def knn_search(
        self, subject_id: str, vector: list[float], k: int = 5
    ) -> list[dict[str, Any]]:
        if not isinstance(k, int) or not 1 <= k <= 100:
            raise ValueError("k must be between 1 and 100")

        columns = SQLModel.metadata.tables["turn"].c
        distance = columns.embedding.cosine_distance(vector).label("distance")
        selected_columns = [
            columns.id,
            columns.subject_id,
            columns.session_id,
            columns.seq,
            columns.ts,
            columns.user_text,
            columns.assistant_text,
            distance,
        ]
        statement = (
            select(*selected_columns)
            .where(columns.subject_id == subject_id)
            .order_by(distance.asc())
            .limit(k)
        )
        async with self._sessions()() as session:
            result = await session.execute(statement)
        return [
            {
                "id": str(row["id"]),
                "subject_id": row["subject_id"],
                "session_id": row["session_id"],
                "seq": row["seq"],
                "ts": row["ts"],
                "user_text": row["user_text"],
                "assistant_text": row["assistant_text"],
                "distance": float(row["distance"]),
            }
            for row in result.mappings().all()
        ]
