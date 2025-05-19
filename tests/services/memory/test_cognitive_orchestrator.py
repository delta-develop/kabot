import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from app.services.memory.cognitive_orchestrator import CognitiveOrchestrator


@pytest.fixture
def orchestrator():
    instance = CognitiveOrchestrator()
    instance.llm = AsyncMock()
    instance.working_memory = AsyncMock()
    instance.fact_memory = AsyncMock()
    instance.episodic_memory = AsyncMock()
    instance.summary_memory = AsyncMock()
    return instance


@pytest.mark.asyncio
async def test_handle_incoming_message_none_intention(orchestrator):
    orchestrator.llm.generate_response.return_value = '{"intention": "none", "response": "Hello!"}'
    orchestrator.working_memory.retrieve_from_memory.return_value = []
    orchestrator.fact_memory.retrieve_from_memory.return_value = ""
    orchestrator.summary_memory.retrieve_from_memory.return_value = ""

    response = await orchestrator.handle_incoming_message("user_1", "Hi there")
    assert response == "Hello!"
    orchestrator.llm.generate_response.assert_awaited()
    orchestrator.working_memory.store_in_memory.assert_awaited()


@pytest.mark.asyncio
async def test_handle_search_intention(orchestrator):
    with patch("app.services.memory.cognitive_orchestrator.perform_vehicle_search", new_callable=AsyncMock) as mock_search, \
         patch("app.services.memory.cognitive_orchestrator.summarize_vehicle_results", new_callable=AsyncMock) as mock_summarize:

        mock_search.return_value = [{"text": "Vehicle info"}]
        mock_summarize.return_value = "Summarize this"
        orchestrator.llm.generate_response.return_value = "Summary done"
        orchestrator.llm.generate_response.reset_mock()

        result = await orchestrator._handle_search_intention("user_1", "Buscar Mazda")

        assert result == "Summary done"
        orchestrator.llm.generate_response.assert_awaited()


@pytest.mark.asyncio
async def test_handle_exit_intention(orchestrator):
    orchestrator.working_memory.retrieve_from_memory.return_value = [
        {"role": "user", "content": "Goodbye"}
    ]
    orchestrator.fact_memory.retrieve_from_memory.return_value = ""
    orchestrator.summary_memory.retrieve_from_memory.return_value = ""
    orchestrator.llm.generate_response.return_value = "See you!"

    result = await orchestrator._handle_exit_intention("user_1", "Bye")

    assert result == "See you!"
    orchestrator.llm.generate_response.assert_awaited()
    orchestrator.working_memory.store_in_memory.assert_awaited()
    orchestrator.episodic_memory.store_in_memory.assert_awaited()