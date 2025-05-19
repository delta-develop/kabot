from typing import Any, Dict, List
from opensearchpy.exceptions import RequestError
from opensearchpy.helpers import async_bulk
from app.services.storage.base import Storage
from app.services.storage.connections import get_open_search_client

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
            if hasattr(record, "model_dump") and callable(getattr(record, "model_dump")):
                doc = record.model_dump()
            else:
                doc = record
            actions.append({"_index": INDEX_NAME, "_source": doc})
        await async_bulk(client, actions)
        return records


