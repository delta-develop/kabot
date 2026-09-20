import asyncio
from unittest.mock import AsyncMock, patch

import pytest

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
    orchestrator.llm.generate_response.return_value = (
        '{"intention": "none", "response": "Hello!"}'
    )
    orchestrator.working_memory.retrieve_from_memory.return_value = []
    orchestrator.fact_memory.retrieve_from_memory.return_value = ""
    orchestrator.summary_memory.retrieve_from_memory.return_value = ""

    response = await orchestrator.handle_incoming_message("user_1", "Hi there")
    assert response == "Hello!"
    orchestrator.llm.generate_response.assert_awaited()
    orchestrator.working_memory.store_in_memory.assert_awaited()


def test_cognitive_orchestrator_naive_flag_initialization():
    default_orchestrator = CognitiveOrchestrator()
    assert default_orchestrator.naive is False

    naive_orchestrator = CognitiveOrchestrator(naive=True)
    assert naive_orchestrator.naive is True


@pytest.mark.asyncio
async def test_cognitive_orchestrator_from_defaults_naive_flag(mocker):
    mocker.patch("app.services.llm.openai_client.OpenAIClient")
    mocker.patch("app.services.memory.working_memory.WorkingMemory")
    mocker.patch("app.services.memory.fact_memory.FactMemory")
    mocker.patch("app.services.memory.episodic_memory.EpisodicMemory")
    mocker.patch("app.services.memory.summary_memory.SummaryMemory")

    default_orc = await CognitiveOrchestrator.from_defaults()
    assert default_orc.naive is False

    naive_orc = await CognitiveOrchestrator.from_defaults(naive=True)
    assert naive_orc.naive is True


@pytest.mark.asyncio
async def test_handle_incoming_message_naive_true(orchestrator):
    orchestrator.naive = True
    orchestrator.episodic_memory.retrieve_from_memory.return_value = [
        {"role": "user", "content": "episodic message"}
    ]
    orchestrator.working_memory.retrieve_from_memory.return_value = [
        {"role": "user", "content": "working message"}
    ]
    orchestrator.fact_memory.retrieve_from_memory.return_value = "User fact"
    orchestrator.summary_memory.retrieve_from_memory.return_value = "User summary"
    orchestrator.llm.generate_response.return_value = (
        '{"intention": "none", "response": "Hello!"}'
    )

    await orchestrator.handle_incoming_message("user_1", "Test input")

    orchestrator.llm.generate_response.assert_awaited_once()
    prompt_messages = orchestrator.llm.generate_response.call_args[0][0]
    context_content = prompt_messages[1]["content"]

    assert "<fact_memory></fact_memory>" in context_content
    assert "<summary_memory></summary_memory>" in context_content
    assert (
        "<working_memory><user>episodic message</user></working_memory>"
        in context_content
    )
    assert "working message" not in context_content
    assert "User fact" not in context_content
    assert "User summary" not in context_content


@pytest.mark.asyncio
async def test_handle_incoming_message_naive_false(orchestrator):
    orchestrator.naive = False
    orchestrator.episodic_memory.retrieve_from_memory.return_value = [
        {"role": "user", "content": "episodic message"}
    ]
    orchestrator.working_memory.retrieve_from_memory.return_value = [
        {"role": "user", "content": "working message"}
    ]
    orchestrator.fact_memory.retrieve_from_memory.return_value = "User fact"
    orchestrator.summary_memory.retrieve_from_memory.return_value = "User summary"
    orchestrator.llm.generate_response.return_value = (
        '{"intention": "none", "response": "Hello!"}'
    )

    await orchestrator.handle_incoming_message("user_1", "Test input")

    orchestrator.llm.generate_response.assert_awaited_once()
    prompt_messages = orchestrator.llm.generate_response.call_args[0][0]
    context_content = prompt_messages[1]["content"]

    assert "<fact_memory>User fact</fact_memory>" in context_content
    assert "<summary_memory>User summary</summary_memory>" in context_content
    assert (
        "<working_memory><user>working message</user></working_memory>"
        in context_content
    )
    assert "episodic message" not in context_content
