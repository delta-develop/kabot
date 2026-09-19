import os
from typing import Any, Dict

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, select

from app.services.storage.base import Storage
from app.models.vehicle import Vehicle


DATABASE_URL = os.getenv(
    "DB_ASYNC_CONNECTION_STR", "postgresql+asyncpg://kabot:kabot123@postgres:5432/kavak"
)

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
    """Asynchronous relational storage implementation using SQLModel and PostgreSQL.

    Attributes:
        engine (AsyncEngine): The asynchronous database engine.
        session_local (sessionmaker): The session factory for async sessions.
    """

    def __init__(self) -> None:
        """Initialize the storage with async engine and session factory."""
        self.engine = engine
        self.session_local = AsyncSessionLocal

    async def setup(self) -> None:
        """Create database tables asynchronously based on SQLModel metadata.

        This method initializes the database schema.
        """
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    async def save(self, data: Dict[str, Any]) -> None:
        """Save a single vehicle record to the database asynchronously.

        Args:
            data (Dict[str, Any]): The data dictionary representing a vehicle.
        """
        async with self.session_local() as session:
            async with session.begin():
                vehicle = Vehicle(**data)
                session.add(vehicle)

    async def get(self, filters: Dict[str, Any]) -> list[Dict[str, Any]]:
        """Query vehicle records asynchronously using filter criteria.

        Args:
            filters (Dict[str, Any]): A dictionary of filter conditions.

        Returns:
            List[Dict[str, Any]]: A list of vehicles matching the filters.
        """
        async with self.session_local() as session:
            statement = select(Vehicle)
            for key, value in filters.items():
                statement = statement.where(getattr(Vehicle, key) == value)
            result = await session.execute(statement)
            vehicles = result.scalars().all()
            return [vehicle.model_dump() for vehicle in vehicles]

    async def bulk_load(self, data: Dict) -> list[Dict[str, Any]]:
        """Bulk load multiple vehicle records into the database asynchronously.

        Args:
            data (Dict): A dictionary containing a 'records' key with a list of vehicle data.

        Returns:
            List[Dict[str, Any]]: The list of loaded vehicle records.
        """
        records = data.get("records", [])
        async with self.session_local() as session:
            async with session.begin():
                for item in records:
                    vehicle = Vehicle(**item)
                    await session.merge(vehicle)
        return records
