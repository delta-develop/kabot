import pytest
from unittest.mock import AsyncMock, patch
from app.services.storage.search_engine_storage import SearchEngineStorage, filters_to_opensearch_clauses

@pytest.mark.asyncio
@patch("app.services.storage.search_engine_storage.get_open_search_client")
async def test_setup_creates_index_if_not_exists(mock_get_client):
    mock_client = AsyncMock()
    mock_get_client.return_value = mock_client
    mock_client.indices.exists.return_value = False

    storage = SearchEngineStorage()
    await storage.setup()

    mock_client.indices.create.assert_called_once()

@pytest.mark.asyncio
@patch("app.services.storage.search_engine_storage.get_open_search_client")
async def test_save_with_dict(mock_get_client):
    mock_client = AsyncMock()
    mock_get_client.return_value = mock_client

    storage = SearchEngineStorage()
    await storage.save({"make": "Mazda"})

    mock_client.index.assert_called_once()

@pytest.mark.asyncio
@patch("app.services.storage.search_engine_storage.get_open_search_client")
async def test_get_with_filters(mock_get_client):
    mock_client = AsyncMock()
    mock_get_client.return_value = mock_client
    mock_client.search.return_value = {
        "hits": {"hits": [{"_source": {"make": "Mazda"}}]}
    }

    storage = SearchEngineStorage()
    result = await storage.get({"make": "Mazda"})

    assert result == [{"make": "Mazda"}]

@pytest.mark.asyncio
@patch("app.services.storage.search_engine_storage.get_open_search_client")
@patch("app.services.storage.search_engine_storage.async_bulk")
async def test_bulk_load(mock_async_bulk, mock_get_client):
    mock_client = AsyncMock()
    mock_get_client.return_value = mock_client
    mock_async_bulk.return_value = ([], [])

    storage = SearchEngineStorage()
    records = [{"make": "Mazda"}, {"make": "Toyota"}]
    result = await storage.bulk_load({"records": records})

    assert result == records

@pytest.mark.asyncio
@patch("app.services.storage.search_engine_storage.get_open_search_client")
async def test_index_with_embedding(mock_get_client):
    mock_client = AsyncMock()
    mock_get_client.return_value = mock_client

    storage = SearchEngineStorage()
    await storage.index_with_embedding("text", {"make": "Mazda"}, [0.1] * 1536)

    mock_client.index.assert_called_once()

@pytest.mark.asyncio
@patch("app.services.storage.search_engine_storage.get_open_search_client")
async def test_knn_search(mock_get_client):
    mock_client = AsyncMock()
    mock_get_client.return_value = mock_client
    mock_client.search.return_value = {
        "hits": {"hits": [{"_source": {"make": "Mazda"}}]}
    }

    storage = SearchEngineStorage()
    result = await storage.knn_search([0.1] * 1536, filters={"filter": []})

    assert result == [{"make": "Mazda"}]

def test_filters_to_opensearch_clauses():
    filters = {
        "make": "Mazda",
        "price": {"lte": 400000},
        "year": 2021,
    }
    clauses = filters_to_opensearch_clauses(filters)
    assert {"term": {"metadata.make": "Mazda"}} in clauses
    assert {"range": {"metadata.price": {"lte": 400000}}} in clauses
    assert {"term": {"metadata.year": 2021}} in clauses