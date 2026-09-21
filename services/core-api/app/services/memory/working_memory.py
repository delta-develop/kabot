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
        # Sessions are keyed by session_id, so deleting a subject needs a
        # reverse index. A SCAN over session:* would be O(n) across every
        # subject in Redis.
        self.subject_index = CacheStorage(namespace="subject_sessions")

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

    async def track_session(self, subject_id: str, session_id: str) -> None:
        """Records that a session belongs to a subject.

        Args:
            subject_id (str): The subject who owns the session.
            session_id (str): The session to index.
        """
        # ponytail: the index outlives the sessions it points at, since session
        # keys carry a TTL and the set does not. Deleting an expired key is a
        # no-op, so it only costs memory; prune on read if a subject ever
        # accumulates enough sessions to matter.
        await self.subject_index.add_to_set(subject_id, session_id)

    async def session_ids(self, subject_id: str) -> list[str]:
        """Returns every session ever opened for a subject.

        Args:
            subject_id (str): The subject to look up.

        Returns:
            list[str]: The indexed session identifiers.
        """
        return await self.subject_index.members(subject_id)

    async def forget_subject(self, subject_id: str) -> None:
        """Deletes every session of a subject along with the index itself.

        Args:
            subject_id (str): The subject to erase.
        """
        for session_id in await self.session_ids(subject_id):
            await self.storage.delete(session_id)
        await self.subject_index.delete(subject_id)
