import pytest
import json
from unittest.mock import AsyncMock, patch

from app.services.memory.fact_memory import FactMemory


@pytest.mark.asyncio
async def test_store_in_memory_merges_and_saves(monkeypatch):
    mock_llm = AsyncMock()
    mock_llm.generate_response.return_value = json.dumps({"name": "Leo", "color_favorito": "verde"})

    mock_storage = AsyncMock()
    mock_storage.get.return_value = {"facts": {"name": "Leo"}}
    mock_storage.save = AsyncMock()

    with patch("app.services.memory.fact_memory.NonRelationalStorage", return_value=mock_storage), \
         patch("app.services.memory.fact_memory.build_fact_merge_prompt", AsyncMock(return_value="prompt")):
        fact_memory = FactMemory(llm=mock_llm)
        await fact_memory.store_in_memory("521123", {"color_favorito": "verde"})

        mock_llm.generate_response.assert_awaited_once()
        mock_storage.save.assert_awaited_once_with({
            "whatsapp_id": "521123",
            "data": {"name": "Leo", "color_favorito": "verde"}
        })


@pytest.mark.asyncio
async def test_retrieve_from_memory_returns_facts():
    mock_llm = AsyncMock()
    mock_storage = AsyncMock()
    mock_storage.get = AsyncMock(return_value={"facts": {"name": "Leo"}})

    with patch("app.services.memory.fact_memory.NonRelationalStorage", return_value=mock_storage):
        fact_memory = FactMemory(llm=mock_llm)
        result = await fact_memory.retrieve_from_memory("521123")

        assert result == {"name": "Leo"}
        mock_storage.get.assert_awaited_once_with({"whatsapp_id": "521123"})


@pytest.mark.asyncio
async def test_retrieve_from_memory_returns_none_when_not_found():
    mock_llm = AsyncMock()
    mock_storage = AsyncMock()
    mock_storage.get = AsyncMock(return_value=None)

    with patch("app.services.memory.fact_memory.NonRelationalStorage", return_value=mock_storage):
        fact_memory = FactMemory(llm=mock_llm)
        result = await fact_memory.retrieve_from_memory("521123")

        assert result is None


@pytest.mark.asyncio
async def test_delete_from_memory():
    mock_llm = AsyncMock()
    mock_storage = AsyncMock()
    mock_storage.delete = AsyncMock()

    with patch("app.services.memory.fact_memory.NonRelationalStorage", return_value=mock_storage):
        fact_memory = FactMemory(llm=mock_llm)
        await fact_memory.delete_from_memory("521123")

        mock_storage.delete.assert_awaited_once_with("521123")