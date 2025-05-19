from abc import ABC, abstractmethod
from typing import Any, Optional


class Memory(ABC):
    @abstractmethod
    async def store_in_memory(self, key: str, data: Any) -> None:
        pass

    @abstractmethod
    async def retrieve_from_memory(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    async def delete_from_memory(self, key: str) -> None:
        pass
