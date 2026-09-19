from abc import ABC, abstractmethod
from typing import Any


class Memory(ABC):
    """Abstract base class for memory storage systems."""

    @abstractmethod
    async def store_in_memory(self, key: str, data: Any) -> None:
        """Stores data in memory associated with a specific key.

        Args:
            key (str): The key used to identify the data.
            data (Any): The data to store.
        """
        pass

    @abstractmethod
    async def retrieve_from_memory(self, key: str) -> Any:
        """Retrieves data from memory using a specific key.

        Args:
            key (str): The key used to identify the data.

        Returns:
            Any: The data associated with the key, or None if not found.
        """
        pass

    @abstractmethod
    async def delete_from_memory(self, key: str) -> None:
        """Deletes data from memory associated with a specific key.

        Args:
            key (str): The key used to identify the data to delete.
        """
        pass
