import json
from app.services.memory.memory import Memory
from app.services.storage.cache_storage import CacheStorage
from typing import Any



class WorkingMemory(Memory):
    """Handles temporary memory using a caching layer."""

    def __init__(self):
        """Initializes the WorkingMemory with a CacheStorage instance."""
        self.storage = CacheStorage()

    async def store_in_memory(self, key: str, data: Any) -> None:
        """Stores data in memory, appending to any existing list.

        Args:
            key (str): The key under which to store the data.
            data (Any): The data to be stored. Must not be a pre-serialized string.
        """
        if isinstance(data, str):
            raise ValueError("Data should not be a pre-serialized string.")
        existing_data = await self.retrieve_from_memory(key)
        if not isinstance(existing_data, list):
            existing_data = []
        if isinstance(data, list):
            existing_data.extend(data)
        else:
            existing_data.append(data)
        await self.storage.set(key, existing_data)

    async def retrieve_from_memory(self, key: str) -> Any:
        """Retrieves and deserializes data from memory by key.

        Args:
            key (str): The key associated with the stored data.

        Returns:
            Any: The retrieved data, or None if not found.
        """
        raw = await self.storage.get(key)
        if raw is None:
            return None
        if isinstance(raw, (list, dict)):
            return raw
        return json.loads(raw)

    async def delete_from_memory(self, key: str) -> None:
        """Deletes data from memory by key.

        Args:
            key (str): The key of the data to delete.
        """
        await self.storage.delete(key)
