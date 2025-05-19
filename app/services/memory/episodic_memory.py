from app.services.memory.memory import Memory
from typing import Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient
import datetime
from app.services.storage.non_relational_storage import NonRelationalStorage


class EpisodicMemory(Memory):
    def __init__(self):
        self.storage = NonRelationalStorage(collection_name="episodic_memory")
        
    async def store_in_memory(self, key: str, data: Any) -> None:
        await self.storage.save({"whatsapp_id": key, "data": data})


    async def retrieve_from_memory(self, key: str) -> Optional[Any]:
        doc = await self.storage.get({"whatsapp_id": key})
        return doc.get("history", []) if doc else []


    async def delete_from_memory(self, key: str) -> None:
        await self.storage.delete(key)
