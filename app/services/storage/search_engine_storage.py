from typing import Any, Dict, List
from opensearchpy import OpenSearch
from opensearchpy.exceptions import RequestError
from app.storage.base import Storage
import time
from opensearchpy import OpenSearch

INDEX_NAME = "vehicles"

MAPPING = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "properties": {
            "stock_id": {"type": "integer"},
            "km": {"type": "integer"},
            "price": {"type": "float"},
            "make": {"type": "keyword"},
            "model": {"type": "keyword"},
            "year": {"type": "integer"},
            "version": {"type": "text", "fields": {"raw": {"type": "keyword"}}},
            "bluetooth": {"type": "boolean"},
            "largo": {"type": "float"},
            "ancho": {"type": "float"},
            "altura": {"type": "float"},
            "car_play": {"type": "boolean"},
        }
    },
}


class SearchEngineStorage(Storage):
    """Storage implementation for OpenSearch."""

    def __init__(self) -> None:
        """Initialize the storage with an OpenSearch client.

        Args:
            None
        """
        self.client = SearchEngineStorage.get_opensearch_client()


    def setup(self) -> None:
        """Create the index with mapping if it doesn't exist."""
        if not self.client.indices.exists(index=INDEX_NAME):
            try:
                self.client.indices.create(index=INDEX_NAME, body=MAPPING)
                print(f"Created index '{INDEX_NAME}'.")
            except RequestError as e:
                print(f"Failed to create index: {e.info}")

    def save(self, data: Dict[str, Any]) -> None:
        """Index a single document into OpenSearch.

        Args:
            data (Dict[str, Any]): The document to index.
        """
        # If the data has a model_dump method (e.g., a Pydantic model), use it
        if hasattr(data, "model_dump") and callable(getattr(data, "model_dump")):
            doc = data.model_dump()
        else:
            doc = data
        self.client.index(index=INDEX_NAME, body=doc)

    def query(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search documents in OpenSearch matching the filters.

        Args:
            filters (Dict[str, Any]): Filter conditions.

        Returns:
            List[Dict[str, Any]]: Matching documents.
        """
        must_clauses = [{"term": {k: v}} for k, v in filters.items()]
        query_body = {"query": {"bool": {"must": must_clauses}}}
        response = self.client.search(index=INDEX_NAME, body=query_body)
        return [hit["_source"] for hit in response["hits"]["hits"]]

    def bulk_load(self, data: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
        """Index multiple documents into OpenSearch.

        Args:
            data (Dict[str, List[Any]]): Dictionary containing a "records" key with a list of documents.

        Returns:
            List[Dict[str, Any]]: The indexed documents.
        """
        from opensearchpy.helpers import bulk

        records = data.get("records", [])
        actions = []
        for record in records:
            # If the record has a model_dump method (e.g., a Pydantic model), use it
            if hasattr(record, "model_dump") and callable(
                getattr(record, "model_dump")
            ):
                doc = record.model_dump()
            else:
                doc = record
            actions.append({"_index": INDEX_NAME, "_source": doc})
        bulk(self.client, actions)
        return records

    @staticmethod
    def get_opensearch_client() -> OpenSearch:
        """Create an OpenSearch client with retry logic.

        Returns:
            OpenSearch: An instance of OpenSearch client.
        """
        from requests.exceptions import RequestException

        max_retries = 6
        delay = 10

        host = 'opensearch-node1'
        port = 9200
        auth = ('admin', 'asfASAS23rae.')

        client = OpenSearch(
            hosts=[{'host': host, 'port': port}],
            http_compress=True,
            http_auth=auth,
            use_ssl=True,
            verify_certs=False,
            ssl_assert_hostname=False,
            ssl_show_warn=False
        )

        for attempt in range(1, max_retries + 1):
            try:
                print(f"[Attempt {attempt}] Trying to connect to OpenSearch...")

                health = client.cluster.health()
                if health["status"] in {"green", "yellow", "red"}:
                    return client

            except Exception as e:
                print(f"Error: {e}. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2

        raise RuntimeError("Failed to connect to OpenSearch after multiple attempts.")