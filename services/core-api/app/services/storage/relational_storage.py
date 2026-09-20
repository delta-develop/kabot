import os
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel, select

from app.models.catalog_item import CatalogItem
from app.services.storage.base import Storage

DATABASE_URL = os.getenv(
    "DB_ASYNC_CONNECTION_STR", "postgresql+asyncpg://kabot:kabot123@postgres:5432/kavak"
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
        async with self._sessions()() as session:
            async with session.begin():
                session.add(CatalogItem(**data))

    async def get(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        async with self._sessions()() as session:
            statement = select(CatalogItem)
            for key, value in filters.items():
                statement = statement.where(getattr(CatalogItem, key) == value)
            result = await session.execute(statement)
            return [item.model_dump() for item in result.scalars().all()]

    async def bulk_load(self, data: dict) -> list[dict[str, Any]]:
        records = data.get("records", [])
        async with self._sessions()() as session:
            async with session.begin():
                session.add_all(CatalogItem(**item) for item in records)
        return records

    async def upsert_items(self, items: list[dict[str, Any]]) -> None:
        statement = insert(CatalogItem).values(items)
        statement = statement.on_conflict_do_update(
            index_elements=[CatalogItem.namespace, CatalogItem.external_id],
            set_={
                "title": statement.excluded.title,
                "body": statement.excluded.body,
                "attributes": statement.excluded.attributes,
                "embedding": statement.excluded.embedding,
            },
        )
        async with self._sessions()() as session:
            async with session.begin():
                await session.execute(statement)

    async def knn_search(
        self,
        namespace: str,
        vector: list[float],
        filters: dict[str, Any] | None = None,
        k: int = 5,
    ) -> list[dict[str, Any]]:
        if not isinstance(k, int) or not 1 <= k <= 100:
            raise ValueError("k must be between 1 and 100")

        columns = SQLModel.metadata.tables["catalog_item"].c
        distance = columns.embedding.cosine_distance(vector).label("distance")
        selected_columns = [
            columns.id,
            columns.namespace,
            columns.external_id,
            columns.title,
            columns.body,
            columns.attributes,
            distance,
        ]
        statement = (
            select(*selected_columns)
            .where(columns.namespace == namespace)
            .order_by(distance.asc())
            .limit(k)
        )
        async with self._sessions()() as session:
            result = await session.execute(statement)
        return [
            {
                "id": str(row["id"]),
                "namespace": row["namespace"],
                "external_id": row["external_id"],
                "title": row["title"],
                "body": row["body"],
                "attributes": row["attributes"],
                "distance": float(row["distance"]),
            }
            for row in result.mappings().all()
        ]
