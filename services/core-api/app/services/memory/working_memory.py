import os
from datetime import datetime

from app.models.session import SessionDocument
from app.services.memory.memory import KeyedMemory
from app.services.storage.cache_storage import CacheStorage
from app.services.storage.connections import get_redis_client

SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "1800"))

# A literal key on purpose, with no namespace and no {id}: this is one global
# index, not a document.
OPEN_SESSIONS_KEY = "open_sessions"


class OpenSessionIndex:
    """The sessions still open, scored by last activity.

    Deliberately not a CacheStorage: that class gets and sets JSON documents
    under `namespace:{id}`, and this is a single sorted set read by score range.
    Folding one into the other would mean pretending a range index and a
    document are the same kind of thing.
    """

    async def add(self, session_id: str, last_activity: datetime) -> None:
        """Marks a session as sweepable from its last activity on.

        Args:
            session_id (str): The session to index.
            last_activity (datetime): The score the sweep compares against.
        """
        redis = await get_redis_client()
        await redis.zadd(OPEN_SESSIONS_KEY, {session_id: last_activity.timestamp()})

    async def remove(self, session_id: str) -> None:
        """Takes a session out of the sweep.

        Args:
            session_id (str): The session to stop sweeping.
        """
        redis = await get_redis_client()
        await redis.zrem(OPEN_SESSIONS_KEY, session_id)

    async def before(self, cutoff: datetime) -> list[str]:
        """Returns the indexed sessions whose last activity predates `cutoff`.

        Args:
            cutoff (datetime): The newest last_activity still considered active.

        Returns:
            list[str]: The session identifiers due for consolidation.
        """
        redis = await get_redis_client()
        return list(await redis.zrangebyscore(OPEN_SESSIONS_KEY, 0, cutoff.timestamp()))


class WorkingMemory(KeyedMemory[SessionDocument]):
    """Handles temporary memory using a caching layer."""

    def __init__(self):
        """Initializes the WorkingMemory with a CacheStorage instance."""
        self.storage = CacheStorage(namespace="session")
        # Sessions are keyed by session_id, so deleting a subject needs a
        # reverse index. A SCAN over session:* would be O(n) across every
        # subject in Redis.
        self.subject_index = CacheStorage(namespace="subject_sessions")
        self.open_index = OpenSessionIndex()

    async def store_in_memory(self, key: str, data: SessionDocument) -> None:
        """Stores a complete session document with a renewed TTL.

        The same write keeps the open-session index current: a session enters it
        while it is open and leaves it the moment it is not, so the sweep never
        re-enqueues a session the worker already took.

        Args:
            key (str): The key under which to store the data.
            data (Any): The session document to store.
        """
        session = SessionDocument.model_validate(data)
        await self.storage.set(
            key, session.model_dump(mode="json"), ttl=SESSION_TTL_SECONDS
        )
        if session.status == "open":
            await self.open_index.add(key, session.last_activity)
        else:
            await self.open_index.remove(key)

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
        await self.drop_from_open(key)

    async def drop_from_open(self, key: str) -> None:
        """Removes a session from the open-session index.

        Args:
            key (str): The session to stop sweeping.
        """
        await self.open_index.remove(key)

    async def open_sessions_before(self, cutoff: datetime) -> list[str]:
        """Returns the open sessions whose last activity predates `cutoff`.

        Args:
            cutoff (datetime): The newest last_activity still considered active.

        Returns:
            list[str]: The session identifiers due for consolidation.
        """
        return await self.open_index.before(cutoff)

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
            await self.drop_from_open(session_id)
        await self.subject_index.delete(subject_id)
