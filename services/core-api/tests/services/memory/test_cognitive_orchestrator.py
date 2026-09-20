from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.models.session import SessionDocument, TurnDraft
from app.services.memory.cognitive_orchestrator import CognitiveOrchestrator


def turn(text: str = "working message", seq: int = 0) -> TurnDraft:
    return TurnDraft(
        seq=seq,
        ts=datetime.now(UTC),
        user_text=text,
        assistant_text="assistant response",
    )


def session(*turns: TurnDraft) -> SessionDocument:
    return SessionDocument(
        subject_id="leo",
        turns=list(turns),
        last_activity=datetime.now(UTC),
    )


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
async def test_handle_incoming_message_returns_direct_reply(orchestrator):
    direct_reply = '{"response": "Hello!"}'
    working_session = session()
    orchestrator.llm.generate_response.return_value = direct_reply
    orchestrator.working_memory.retrieve_from_memory.return_value = working_session
    orchestrator.fact_memory.retrieve_from_memory.return_value = ""
    orchestrator.summary_memory.retrieve_from_memory.return_value = ""

    response = await orchestrator.handle_incoming_message(
        "leo", "session-id", "Hi there"
    )

    assert response == direct_reply
    stored_session = orchestrator.working_memory.store_in_memory.call_args.args[1]
    assert stored_session.turns[0].seq == 0
    assert stored_session.turns[0].assistant_text == direct_reply


def test_cognitive_orchestrator_naive_flag_initialization():
    assert CognitiveOrchestrator().naive is False
    assert CognitiveOrchestrator(naive=True).naive is True


@pytest.mark.asyncio
async def test_cognitive_orchestrator_from_defaults_naive_flag(mocker):
    mocker.patch("app.services.llm.openai_client.OpenAIClient")
    mocker.patch("app.services.memory.working_memory.WorkingMemory")
    mocker.patch("app.services.memory.fact_memory.FactMemory")
    mocker.patch("app.services.memory.episodic_memory.EpisodicMemory")
    mocker.patch("app.services.memory.summary_memory.SummaryMemory")

    assert (await CognitiveOrchestrator.from_defaults()).naive is False
    assert (await CognitiveOrchestrator.from_defaults(naive=True)).naive is True


@pytest.mark.asyncio
async def test_handle_incoming_message_naive_true(orchestrator):
    orchestrator.naive = True
    orchestrator.episodic_memory.retrieve_from_memory.return_value = [
        turn("episodic message")
    ]
    orchestrator.working_memory.retrieve_from_memory.return_value = session(
        turn("working message")
    )
    orchestrator.fact_memory.retrieve_from_memory.return_value = "User fact"
    orchestrator.summary_memory.retrieve_from_memory.return_value = "User summary"
    orchestrator.llm.generate_response.return_value = "Hello!"

    await orchestrator.handle_incoming_message("leo", "session-id", "Test input")

    prompt_messages = orchestrator.llm.generate_response.call_args.args[0]
    context_content = prompt_messages[1]["content"]
    assert "<fact_memory></fact_memory>" in context_content
    assert "<summary_memory></summary_memory>" in context_content
    assert "<user>episodic message</user>" in context_content
    assert "working message" not in context_content
    assert "User fact" not in context_content
    assert "User summary" not in context_content


@pytest.mark.asyncio
async def test_handle_incoming_message_uses_subject_context_once(orchestrator):
    orchestrator.working_memory.retrieve_from_memory.return_value = session(
        turn("working message")
    )
    orchestrator.fact_memory.retrieve_from_memory.return_value = "User fact"
    orchestrator.summary_memory.retrieve_from_memory.return_value = "User summary"
    orchestrator.llm.generate_response.return_value = "Hello!"

    await orchestrator.handle_incoming_message("leo", "session-id", "Test input")

    context_content = orchestrator.llm.generate_response.call_args.args[0][1]["content"]
    assert context_content.count("User fact") == 1
    assert context_content.count("User summary") == 1
    assert "<user>working message</user>" in context_content
    assert "episodic message" not in context_content


@pytest.mark.asyncio
async def test_handle_incoming_message_rejects_missing_session(orchestrator):
    orchestrator.working_memory.retrieve_from_memory.return_value = None

    with pytest.raises(KeyError, match="missing-session"):
        await orchestrator.handle_incoming_message("leo", "missing-session", "Hello")

    orchestrator.llm.generate_response.assert_not_awaited()


@pytest.mark.asyncio
async def test_subject_memory_survives_between_sessions(orchestrator):
    session_a = session(turn("My favorite color is green"))
    session_b = session()
    orchestrator.working_memory.retrieve_from_memory.side_effect = [
        session_a,
        session_b,
    ]

    await orchestrator.persist_conversation_closure("leo", "session-a")

    stored_turn = session_a.turns[0].model_dump(mode="json")
    orchestrator.episodic_memory.store_in_memory.assert_awaited_once_with(
        "leo", [{"session_id": "session-a", **stored_turn}]
    )
    orchestrator.fact_memory.store_in_memory.assert_awaited_once_with(
        "leo", session_a.turns
    )
    orchestrator.summary_memory.store_in_memory.assert_awaited_once_with(
        "leo", session_a.turns
    )
    orchestrator.working_memory.delete_from_memory.assert_awaited_once_with("session-a")

    orchestrator.fact_memory.retrieve_from_memory.return_value = "Favorite color: green"
    orchestrator.summary_memory.retrieve_from_memory.return_value = "Prior conversation"
    orchestrator.llm.generate_response.return_value = "Welcome back"

    await orchestrator.handle_incoming_message("leo", "session-b", "Hello again")

    context = orchestrator.llm.generate_response.call_args.args[0][1]["content"]
    assert "Favorite color: green" in context
    assert "Prior conversation" in context
    assert "<working_memory></working_memory>" in context
