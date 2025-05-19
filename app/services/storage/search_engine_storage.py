from typing import Any, Dict, List
from opensearchpy.exceptions import RequestError
from opensearchpy.helpers import async_bulk
from app.services.storage.base import Storage
from app.services.storage.connections import get_open_search_client

INDEX_NAME = "vehicles"

MAPPING = {
    "settings": {
        "index": {"knn": True, "number_of_shards": 1, "number_of_replicas": 0}
    },
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
            "embedding": {
                "type": "knn_vector",
                "dimension": 1536,
                "method": {
                    "name": "hnsw",
                    "engine": "faiss",
                    "space_type": "cosinesimil",
                },
            },
            "text": {"type": "text"},
            "metadata": {"type": "object", "enabled": True},
        }
    },
}


class SearchEngineStorage(Storage):
    """Asynchronous storage implementation for OpenSearch using a singleton client."""

    async def setup(self) -> None:
        """Asynchronously create the index with mapping if it doesn't exist."""
        client = await get_open_search_client()
        exists = await client.indices.exists(index=INDEX_NAME)
        if not exists:
            try:
                await client.indices.create(index=INDEX_NAME, body=MAPPING)
            except RequestError as e:
                print(f"Failed to create index: {e.info}")

    async def save(self, data: Dict[str, Any]) -> None:
        """Index a single document into OpenSearch asynchronously."""
        client = await get_open_search_client()
        if hasattr(data, "model_dump") and callable(getattr(data, "model_dump")):
            doc = data.model_dump()
        else:
            doc = data
        await client.index(index=INDEX_NAME, body=doc)

    async def get(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search documents in OpenSearch matching the filters asynchronously."""
        client = await get_open_search_client()
        must_clauses = [{"term": {k: v}} for k, v in filters.items()]
        query_body = {"query": {"bool": {"must": must_clauses}}}
        response = await client.search(index=INDEX_NAME, body=query_body)
        return [hit["_source"] for hit in response["hits"]["hits"]]

    async def bulk_load(self, data: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
        """Index multiple documents into OpenSearch asynchronously."""
        client = await get_open_search_client()
        records = data.get("records", [])
        actions = []
        for record in records:
            if hasattr(record, "model_dump") and callable(
                getattr(record, "model_dump")
            ):
                doc = record.model_dump()
            else:
                doc = record
            actions.append({"_index": INDEX_NAME, "_source": doc})
        await async_bulk(client, actions)
        return records

    async def index_with_embedding(
        self, text: str, metadata: dict, vector: list[float]
    ) -> None:
        """
        Indexes a document with a vector embedding into OpenSearch.

        Args:
            text (str): Textual content of the document.
            metadata (dict): Metadata associated with the document.
            vector (list[float]): Embedding vector to be indexed.
        """
        client = await get_open_search_client()
        body = {"text": text, "embedding": vector, "metadata": metadata}
        await client.index(index=INDEX_NAME, body=body)

    async def knn_search(
        self, vector: list[float], k: int = 5, filters: dict = None
    ) -> List[Dict[str, Any]]:
        """
        Performs a k-Nearest Neighbors (k-NN) search on OpenSearch.

        Args:
            vector (list[float]): Query embedding vector.
            k (int, optional): Number of nearest neighbors to retrieve. Defaults to 5.
            filters (dict, optional): Additional OpenSearch boolean filter clauses.

        Returns:
            List[Dict[str, Any]]: List of documents matching the vector and filters.
        """
        client = await get_open_search_client()
        knn_clause = {"knn": {"embedding": {"vector": vector, "k": k}}}

        # The filters argument is expected to be a bool block (already formatted)
        query = {
            "size": k,
            "_source": {"excludes": ["embedding"]},
            "query": {
                "bool": {
                    **(filters if isinstance(filters, dict) else {}),
                    "must": [knn_clause],
                }
            },
        }

        print(f"query: {query}")
        response = await client.search(index=INDEX_NAME, body=query)
        return [hit["_source"] for hit in response["hits"]["hits"]]


# Helper function to convert filters dict to OpenSearch clauses
def filters_to_opensearch_clauses(filters: dict) -> list:
    """
    Converts a dictionary of filters into OpenSearch query clauses.

    Args:
        filters (dict): Dictionary containing filter keys and values.

    Returns:
        list: A list of OpenSearch-compatible query clauses.
    """
    clauses = []
    for key, value in filters.items():
        # Los campos están dentro de "metadata", excepto "embedding" y "text"
        field = f"metadata.{key}" if key not in {"embedding", "text"} else key
        if isinstance(value, dict) and any(
            k in value for k in ["lte", "gte", "lt", "gt"]
        ):
            clauses.append({"range": {field: value}})
        else:
            clauses.append({"term": {field: value}})
    return clauses
