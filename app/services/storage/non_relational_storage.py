from datetime import datetime
from typing import Any, Dict, List

from app.services.storage.base import Storage
from app.services.storage.connections import get_mongo_client


class NonRelationalStorage(Storage):
    """Non-relational storage implementation using MongoDB."""

    def __init__(self, collection_name: str) -> None:
        """
        Initialize NonRelationalStorage with a specific MongoDB collection.

        Args:
            collection_name (str): The name of the MongoDB collection to interact with.
        """
        self.collection_name = collection_name
        self.save_methods = {
            "episodic_memory": self._save_episodic_memory,
            "fact_memory": self._save_fact_memory,
            "summary_memory": self._save_summary_memory,
        }

    async def setup(self) -> None:
        """
        Initialize the MongoDB collection handle.
        """
        client = await get_mongo_client()
        self.collection = client.get_default_database()[self.collection_name]

    async def save(self, data: Dict[str, Any]) -> None:
        """
        Save data to the appropriate memory type based on the collection.

        Args:
            data (Dict[str, Any]): Data payload containing whatsapp_id and memory content.

        Raises:
            ValueError: If the collection name is invalid.
        """
        save_function = self.save_methods.get(self.collection_name)

        if not save_function:
            raise ValueError(f"Invalid collection name: {self.collection_name}")

        await save_function(data)

    async def get(self, filters: Dict[str, Any]) -> Dict[str, Any] | None:
        """
        Retrieve a document from the MongoDB collection based on filters.

        Args:
            filters (Dict[str, Any]): Query filters.

        Returns:
            Dict[str, Any] | None: Retrieved document or None if not found.
        """
        client = await get_mongo_client()
        coll = client.get_default_database()[self.collection_name]
        return await coll.find_one(filters, projection={"_id": 0})

    async def bulk_load(self, data: Dict) -> List[Dict[str, Any]]:
        """
        Bulk load placeholder method.

        Args:
            data (Dict): Data to bulk load.

        Returns:
            List[Dict[str, Any]]: List of results (not implemented).
        """
        pass

    async def delete(self, key: str) -> None:
        """
        Delete a document from the MongoDB collection by whatsapp_id.

        Args:
            key (str): The whatsapp_id of the document to delete.
        """
        client = await get_mongo_client()
        coll = client.get_default_database()[self.collection_name]
        await coll.delete_one({"whatsapp_id": key})

    async def _save_episodic_memory(self, payload):
        """
        Save a list of message objects into `history` preserving FIFO order.

        Args:
            payload (dict): Dictionary with keys 'whatsapp_id' and 'data' where data is a list of messages.

        Raises:
            ValueError: If `data` is not a list.
        """
        key = payload["whatsapp_id"]
        messages = payload["data"]
        if not isinstance(messages, list):
            raise ValueError(
                "EpisodicMemory expects `data` to be a list of message objects"
            )

        client = await get_mongo_client()
        coll = client.get_default_database()[self.collection_name]
        await coll.update_one(
            {"whatsapp_id": key},
            {
                "$push": {"history": {"$each": messages}},
                "$set": {"last_updated": datetime.utcnow().isoformat()},
            },
            upsert=True,
        )

    async def _save_fact_memory(self, payload):
        """
        Replace the entire `facts` object.

        Args:
            payload (dict): Dictionary with keys 'whatsapp_id' and 'data' representing facts to store.
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
        Replace the summary text.

        Args:
            payload (dict): Dictionary with keys 'whatsapp_id' and 'data' containing the summary string.
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
