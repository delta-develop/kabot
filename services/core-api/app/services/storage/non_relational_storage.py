from typing import Any

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

    async def setup(self) -> None:
        """
        Initialize the MongoDB collection handle.
        """
        client = await get_mongo_client()
        self.collection = client.get_default_database()[self.collection_name]

    async def save(self, data: dict[str, Any]) -> None:
        """Replace one keyed document in the configured collection."""
        client = await get_mongo_client()
        coll = client.get_default_database()[self.collection_name]
        await coll.replace_one({"subject_id": data["subject_id"]}, data, upsert=True)

    async def get(self, filters: dict[str, Any]) -> dict[str, Any] | None:
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

    async def delete(self, key: str) -> None:
        """
        Delete a document from the MongoDB collection by subject_id.

        Args:
            key (str): The subject_id of the document to delete.
        """
        client = await get_mongo_client()
        coll = client.get_default_database()[self.collection_name]
        await coll.delete_one({"subject_id": key})
