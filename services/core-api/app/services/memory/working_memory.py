import os

from app.models.session import SessionDocument
from app.services.memory.memory import KeyedMemory
from app.services.storage.cache_storage import CacheStorage

SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "1800"))


class WorkingMemory(KeyedMemory[SessionDocument]):
    """Handles temporary memory using a caching layer."""

    def __init__(self):
        """Initializes the WorkingMemory with a CacheStorage instance."""
        self.storage = CacheStorage(namespace="session")

    async def store_in_memory(self, key: str, data: SessionDocument) -> None:
        """Stores a complete session document with a renewed TTL.

        Args:
            key (str): The key under which to store the data.
            data (Any): The session document to store.
        """
        session = SessionDocument.model_validate(data)
        await self.storage.set(
            key, session.model_dump(mode="json"), ttl=SESSION_TTL_SECONDS
        )

    async def retrieve_from_memory(self, key: str) -> SessionDocument | None:
        """Retrieves and deserializes data from memory by key.

        Args:
            key (str): The key associated with the stored data.

        Returns:
            Any: The retrieved data, or None if not found.
        """
        raw = await self.storage.get(key)
        if raw is None:
            return None
        return SessionDocument.model_validate(raw)

    async def delete_from_memory(self, key: str) -> None:
        """Deletes data from memory by key.

        Args:
            key (str): The key of the data to delete.
        """
        await self.storage.delete(key)
