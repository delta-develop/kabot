import os
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, select

from app.services.storage.base import Storage
from app.models.vehicle import Vehicle

# Use asyncpg driver for true async support
DATABASE_URL = os.getenv(
    "DB_ASYNC_CONNECTION_STR",
    "postgresql+asyncpg://kabot:kabot123@postgres:5432/kavak"
)

# Create an async engine and session factory
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=True,
    future=True,
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class RelationalStorage(Storage):
    """Asynchronous relational storage implementation using SQLModel and PostgreSQL."""

    def __init__(self) -> None:
        """Initialize with the async engine and session factory."""
        self.engine = engine
        self.session_local = AsyncSessionLocal

    async def setup(self) -> None:
        """Asynchronously create database tables based on SQLModel metadata."""
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    async def save(self, data: Dict[str, Any]) -> None:
        """Asynchronously save a single vehicle record to the database."""
        async with self.session_local() as session:
            async with session.begin():
                vehicle = Vehicle(**data)
                session.add(vehicle)

    async def get(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Asynchronously query vehicle records using filter criteria."""
        async with self.session_local() as session:
            statement = select(Vehicle)
            for key, value in filters.items():
                statement = statement.where(getattr(Vehicle, key) == value)
            result = await session.execute(statement)
            vehicles = result.scalars().all()
            return [vehicle.model_dump() for vehicle in vehicles]

    async def bulk_load(self, data: Dict) -> List[Dict[str, Any]]:
        """Asynchronously bulk load multiple vehicle records into the database."""
        records = data.get("records", [])
        async with self.session_local() as session:
            async with session.begin():
                vehicles = [Vehicle(**item) for item in records]
                session.add_all(vehicles)
        return [vehicle.model_dump() for vehicle in vehicles]
