from abc import ABC, abstractmethod
from typing import Any, Dict, List


class Storage(ABC):
    @abstractmethod
    async def save(self, data: Dict[str, Any]) -> None:
        """Asynchronously save a single item to the storage backend.

        Args:
            data (Dict[str, Any]): The data to store.
        """
        pass

    @abstractmethod
    async def get(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Asynchronously get records from the storage using filter criteria."""
        pass

    @abstractmethod
    async def bulk_load(self, data: Dict) -> List[Dict[str, Any]]:
        """Asynchronously load multiple records into the storage backend.

        Args:
            data (Dict): The data to be bulk uploaded.

        Returns:
            List[Dict[str, Any]]: A list of loaded records.
        """
        pass

    @abstractmethod
    async def setup(self) -> None:
        """Perform asynchronous setup operations such as creating tables or indices."""
        pass
