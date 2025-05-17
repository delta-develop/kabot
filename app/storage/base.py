from abc import ABC, abstractmethod
from typing import Any, Dict, List


class Storage(ABC):
    @abstractmethod
    def save(self, data: Dict[str, Any]) -> None:
        """Save a single item to the storage backend.

        Args:
            data (Dict[str, Any]): The data to store.
        """
        pass

    @abstractmethod
    def query(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query the storage using filter criteria.

        Args:
            filters (Dict[str, Any]): A dictionary of query filters.

        Returns:
            List[Dict[str, Any]]: A list of matching records.
        """
        pass

    @abstractmethod
    def bulk_load(self, data: Dict) -> List[Dict[str, Any]]:
        """Load multiple records from the storage backend based on a key.

        Args:
            data (Dict): The data to be bulk uploaded.

        Returns:
            List[Dict[str, Any]]: A list of loaded records.
        """
        pass

    @abstractmethod
    def setup(self) -> None:
        """Perform setup operations such as creating tables or indices."""
        pass
