from app.models.session import TurnDraft
from app.services.memory.memory import Memory
from app.services.storage.non_relational_storage import NonRelationalStorage


class EpisodicMemory(Memory):
    """Manages episodic memory storage and retrieval for subjects.

    This class provides methods to store, retrieve, and delete episodic memory data
    associated with a subject.
    """

    def __init__(self):
        """Initializes the EpisodicMemory instance with a non-relational storage backend.

        The storage is configured to use the 'episodic_memory' collection.
        """
        self.storage = NonRelationalStorage(collection_name="episodic_memory")

    async def store_in_memory(self, key: str, data) -> None:
        """Stores episodic memory data for a specified user key.

        Args:
            key (str): Unique identifier for the subject.
            data: The memory data to be stored.
        """
        await self.storage.save({"subject_id": key, "data": data})

    async def retrieve_from_memory(self, key: str) -> list[TurnDraft]:
        """Retrieves episodic memory history for the specified user key.

        Args:
            key (str): Unique identifier for the subject.

        Returns:
            list[TurnDraft]: The subject's history, or an empty list.
        """
        doc = await self.storage.get({"subject_id": key})
        return (
            [TurnDraft.model_validate(turn) for turn in doc.get("history", [])]
            if doc
            else []
        )

    async def delete_from_memory(self, key: str) -> None:
        """Deletes episodic memory associated with the specified user key.

        Args:
            key (str): Unique identifier for the subject.
        """
        await self.storage.delete(key)
