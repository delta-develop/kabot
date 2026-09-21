from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from app.models.turn import Fragment, Turn

T = TypeVar("T")


class KeyedMemory(ABC, Generic[T]):
    """Keyed access: one key stores and retrieves one value."""

    @abstractmethod
    async def store_in_memory(self, key: str, data: T) -> None:
        pass

    @abstractmethod
    async def retrieve_from_memory(self, key: str) -> T | None:
        pass

    @abstractmethod
    async def delete_from_memory(self, key: str) -> None:
        pass


class EpisodicLog(ABC):
    """Append-only turn log with ordered history access."""

    @abstractmethod
    async def append(self, turns: list[Turn]) -> None:
        pass

    @abstractmethod
    async def history(self, subject_id: str, limit: int | None = None) -> list[Turn]:
        pass

    @abstractmethod
    async def has_turns(
        self, subject_id: str, exclude_session: str | None = None
    ) -> bool:
        pass

    @abstractmethod
    async def by_session(
        self, session_id: str, limit: int, offset: int = 0
    ) -> list[Turn]:
        pass

    @abstractmethod
    async def delete(self, subject_id: str) -> None:
        pass

    @abstractmethod
    async def similar(
        self,
        subject_id: str,
        vector: list[float],
        k: int,
        exclude_session: str | None = None,
    ) -> list[Fragment]:
        pass
