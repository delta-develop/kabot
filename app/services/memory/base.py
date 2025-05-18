from abc import ABC, abstractmethod
from typing import Any, Optional


class WorkingMemoryBase(ABC):
    """Abstract interface for memory/cache systems."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Retrieve a value by key."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = 0) -> None:
        """Store a value with an optional time-to-live (TTL) in seconds."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove a key from the cache."""
        pass