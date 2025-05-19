from datetime import datetime
from typing import Any, Dict, List
from app.services.storage.base import Storage
from app.services.storage.connections import get_mongo_client


class NonRelationalStorage(Storage):
    """Non-relational storage implementation using MongoDB."""

    def __init__(self, collection_name: str) -> None:
        self.collection_name = collection_name
        self.save_methods = {
            "episodic_memory": self._save_episodic_memory,
            "fact_memory": self._save_fact_memory,
            "summary_memory": self._save_summary_memory
        }


    async def setup(self) -> None:
        """Initialize the MongoDB collection handle."""
        client = await get_mongo_client()
        self.collection = client.get_default_database()[self.collection_name]

    async def save(self, data: Dict[str, Any]) -> None:
        save_function = self.save_methods.get(self.collection_name)
        
        if not save_function:
            raise ValueError(f"Invalid collection name: {self.collection_name}")
        
        await save_function(data)
        

    async def get(self, filters: Dict[str, Any]) -> Dict[str, Any] | None:
        """Return the full document (without _id) that matches the filter."""
        client = await get_mongo_client()
        coll = client.get_default_database()[self.collection_name]
        return await coll.find_one(filters, projection={"_id": 0})

    async def bulk_load(self, data: Dict) -> List[Dict[str, Any]]:
        """Bulk load placeholder - implement as needed."""
        pass

    async def delete(self, key: str) -> None:
        client = await get_mongo_client()
        coll = client.get_default_database()[self.collection_name]
        await coll.delete_one({"whatsapp_id": key})
        
    async def _save_episodic_memory(self, payload):
        """
        Save a list of message objects into `history` preserving FIFO order.
        Expected shape: {"whatsapp_id": str, "data": [ {...}, {...} ]}
        """
        key = payload["whatsapp_id"]
        messages = payload["data"]
        if not isinstance(messages, list):
            raise ValueError("EpisodicMemory expects `data` to be a list of message objects")

        client = await get_mongo_client()
        coll = client.get_default_database()[self.collection_name]
        await coll.update_one(
            {"whatsapp_id": key},
            {
                "$push": {"history": {"$each": messages}},  # FIFO: add at end
                "$set": {"last_updated": datetime.utcnow().isoformat()},
            },
            upsert=True,
        )
    
    async def _save_fact_memory(self, payload):
        """
        Replace the entire `facts` object. Shape: {"whatsapp_id": str, "data": {...}}
        """
        key = payload["whatsapp_id"]
        new_facts = payload["data"]

        client = await get_mongo_client()
        coll = client.get_default_database()[self.collection_name]
        await coll.update_one(
            {"whatsapp_id": key},
            {
                "$set": {
                    "facts": new_facts,
                    "last_updated": datetime.utcnow().isoformat(),
                }
            },
            upsert=True,
        )
    
    async def _save_summary_memory(self, payload):
        """
        Replace the summary text. Shape: {"whatsapp_id": str, "data": str}
        """
        key = payload["whatsapp_id"]
        summary_text = payload["data"]

        client = await get_mongo_client()
        coll = client.get_default_database()[self.collection_name]
        await coll.update_one(
            {"whatsapp_id": key},
            {
                "$set": {
                    "summary": summary_text,
                    "last_updated": datetime.utcnow().isoformat(),
                }
            },
            upsert=True,
        )