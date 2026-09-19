from typing import Optional

from app.services.memory.memory import Memory
from app.services.storage.non_relational_storage import NonRelationalStorage


class EpisodicMemory(Memory):
    """Manages episodic memory storage and retrieval for user sessions.

    This class provides methods to store, retrieve, and delete episodic memory data 
    associated with a unique user key, typically a session identifier such as a WhatsApp ID.
    """

    def __init__(self):
        """Initializes the EpisodicMemory instance with a non-relational storage backend.

        The storage is configured to use the 'episodic_memory' collection.
        """
        self.storage = NonRelationalStorage(collection_name="episodic_memory")

    async def store_in_memory(self, key: str, data) -> None:
        """Stores episodic memory data for a specified user key.

        Args:
            key (str): Unique identifier for the user's session (e.g., WhatsApp ID).
            data: The memory data to be stored.
        """
        await self.storage.save({"whatsapp_id": key, "data": data})

    async def retrieve_from_memory(self, key: str) -> Optional:
        """Retrieves episodic memory history for the specified user key.

        Args:
            key (str): Unique identifier for the user's session.

        Returns:
            Optional: A list representing the memory history if found; otherwise, an empty list.
        """
        doc = await self.storage.get({"whatsapp_id": key})
        return doc.get("history", []) if doc else []

    async def delete_from_memory(self, key: str) -> None:
        """Deletes episodic memory associated with the specified user key.

        Args:
            key (str): Unique identifier for the user's session.
        """
        await self.storage.delete(key)
