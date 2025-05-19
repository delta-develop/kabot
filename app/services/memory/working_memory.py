from app.services.memory.memory import Memory
from app.services.storage.cache_storage import CacheStorage
from typing import Any, Optional
import json


class WorkingMemory(Memory):
    def __init__(self):
        self.storage = CacheStorage()

    async def store_in_memory(self, key: str, data: Any) -> None:
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

    async def retrieve_from_memory(self, key: str) -> Optional[Any]:
        raw = await self.storage.get(key)
        if raw is None:
            return None
        if isinstance(raw, (list, dict)):  # ya está deserializado
            return raw
        return json.loads(raw)

    async def delete_from_memory(self, key: str) -> None:
        await self.storage.delete(key)
