import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.models.session import TurnDraft
from app.services.memory.fact_memory import FactMemory


@pytest.mark.asyncio
async def test_store_in_memory_merges_and_saves():
    mock_llm = AsyncMock()
    mock_llm.generate_response.return_value = json.dumps(
        {"name": "Leo", "favorite_color": "green"}
    )

    mock_storage = AsyncMock()
    mock_storage.get.return_value = {"facts": {"name": "Leo"}}
    mock_storage.save = AsyncMock()

    with patch(
        "app.services.memory.fact_memory.NonRelationalStorage",
        return_value=mock_storage,
    ):
        fact_memory = FactMemory(llm=mock_llm)
        recent_turns = [
            TurnDraft(
                seq=0,
                ts=datetime.now(UTC),
                user_text="My favorite color is green",
                assistant_text="Noted",
            )
        ]
        await fact_memory.store_in_memory("subject-123", recent_turns)

        mock_llm.generate_response.assert_awaited_once()
        prompt = mock_llm.generate_response.call_args.args[0][0]["content"]
        assert "user: My favorite color is green" in prompt
        assert "assistant: Noted" in prompt
        saved = mock_storage.save.await_args.args[0]
        assert saved["subject_id"] == "subject-123"
        assert saved["facts"] == {"name": "Leo", "favorite_color": "green"}
        assert saved["last_updated"]


@pytest.mark.asyncio
async def test_retrieve_from_memory_returns_facts():
    mock_llm = AsyncMock()
    mock_storage = AsyncMock()
    mock_storage.get = AsyncMock(return_value={"facts": {"name": "Leo"}})

    with patch(
        "app.services.memory.fact_memory.NonRelationalStorage",
        return_value=mock_storage,
    ):
        fact_memory = FactMemory(llm=mock_llm)
        result = await fact_memory.retrieve_from_memory("subject-123")

        assert result == {"name": "Leo"}
        mock_storage.get.assert_awaited_once_with({"subject_id": "subject-123"})


@pytest.mark.asyncio
async def test_retrieve_from_memory_returns_none_when_not_found():
    mock_llm = AsyncMock()
    mock_storage = AsyncMock()
    mock_storage.get = AsyncMock(return_value=None)

    with patch(
        "app.services.memory.fact_memory.NonRelationalStorage",
        return_value=mock_storage,
    ):
        fact_memory = FactMemory(llm=mock_llm)
        result = await fact_memory.retrieve_from_memory("subject-123")

        assert result is None


@pytest.mark.asyncio
async def test_delete_from_memory():
    mock_llm = AsyncMock()
    mock_storage = AsyncMock()
    mock_storage.delete = AsyncMock()

    with patch(
        "app.services.memory.fact_memory.NonRelationalStorage",
        return_value=mock_storage,
    ):
        fact_memory = FactMemory(llm=mock_llm)
        await fact_memory.delete_from_memory("subject-123")

        mock_storage.delete.assert_awaited_once_with("subject-123")


@pytest.mark.asyncio
async def test_malformed_json_keeps_the_stored_facts_and_does_not_raise():
    """A bad merge must not abort the closure that carries the summary too."""
    mock_llm = AsyncMock()
    mock_llm.generate_response.return_value = '{"name": "Leo", broken'

    mock_storage = AsyncMock()
    mock_storage.get.return_value = {"facts": {"name": "Leo"}}

    with patch(
        "app.services.memory.fact_memory.NonRelationalStorage",
        return_value=mock_storage,
    ):
        fact_memory = FactMemory(llm=mock_llm)

        await fact_memory.store_in_memory("subject-123", [])

        mock_storage.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_fact_merge_asks_the_model_for_json():
    """Asking for JSON in the prompt is a request; response_format is a guarantee."""
    mock_llm = AsyncMock()
    mock_llm.generate_response.return_value = json.dumps({"name": "Leo"})
    mock_storage = AsyncMock()
    mock_storage.get.return_value = {"facts": {}}

    with patch(
        "app.services.memory.fact_memory.NonRelationalStorage",
        return_value=mock_storage,
    ):
        await FactMemory(llm=mock_llm).store_in_memory("subject-123", [])

    assert mock_llm.generate_response.await_args.kwargs["as_json"] is True
