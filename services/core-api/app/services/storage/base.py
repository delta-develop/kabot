from abc import ABC, abstractmethod
from typing import Any


class Storage(ABC):
    @abstractmethod
    async def save(self, data: dict[str, Any]) -> None:
        """Asynchronously save a single item to the storage backend.

        Args:
            data (Dict[str, Any]): The data to store.
        """
        pass

    @abstractmethod
    async def setup(self) -> None:
        """Perform asynchronous setup operations such as creating tables or indices."""
        pass
