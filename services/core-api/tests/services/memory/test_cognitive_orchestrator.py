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
    # Without this the assembler would treat the mock's truthy return as real
    # history and reach for a live embedding.
    instance.episodic_memory.has_turns.return_value = False
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

    response, context = await orchestrator.handle_incoming_message(
        "leo", "session-id", "Hi there"
    )

    assert response == direct_reply
    assert context is not None
    assert context.used <= context.budget
    stored_session = orchestrator.working_memory.store_in_memory.call_args.args[1]
    assert stored_session.turns[0].seq == 0
    assert stored_session.turns[0].assistant_text == direct_reply


@pytest.mark.asyncio
async def test_turn_sequence_is_monotonic_within_session(orchestrator):
    working_session = session()
    orchestrator.working_memory.retrieve_from_memory.return_value = working_session
    orchestrator.fact_memory.retrieve_from_memory.return_value = ""
    orchestrator.summary_memory.retrieve_from_memory.return_value = ""
    orchestrator.llm.generate_response.return_value = "reply"

    await orchestrator.handle_incoming_message("leo", "session-id", "first")
    await orchestrator.handle_incoming_message("leo", "session-id", "second")

    assert [item.seq for item in working_session.turns] == [0, 1]


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
async def test_naive_history_prompt_starts_with_first_turn_of_first_session(
    orchestrator,
):
    orchestrator.naive = True
    orchestrator.episodic_memory.history.return_value = [
        turn("first turn of first session", seq=0),
        turn("last turn of latest session", seq=1),
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
    assert "## hechos" not in context_content
    assert "## resumen" not in context_content
    assert "User: first turn of first session" in context_content
    assert "User: last turn of latest session" in context_content
    assert context_content.index("first turn of first session") < context_content.index(
        "last turn of latest session"
    )
    assert "working message" not in context_content
    assert "User fact" not in context_content
    assert "User summary" not in context_content
    orchestrator.episodic_memory.history.assert_awaited_once_with("leo")


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
    assert "User: working message" in context_content
    assert "episodic message" not in context_content


@pytest.mark.asyncio
async def test_handle_incoming_message_rejects_missing_session(orchestrator):
    orchestrator.working_memory.retrieve_from_memory.return_value = None

    with pytest.raises(KeyError, match="missing-session"):
        await orchestrator.handle_incoming_message("leo", "missing-session", "Hello")

    orchestrator.llm.generate_response.assert_not_awaited()


@pytest.mark.asyncio
async def test_subject_memory_survives_between_sessions(orchestrator, mocker):
    session_a = session(turn("My favorite color is green"))
    original_turns = list(session_a.turns)
    session_b = session()
    orchestrator.working_memory.retrieve_from_memory.side_effect = [
        session_a,
        session_b,
    ]
    get_embeddings = mocker.patch(
        "app.services.memory.cognitive_orchestrator.get_embeddings",
        AsyncMock(return_value=[[0.0] * 1536]),
    )

    await orchestrator.persist_conversation_closure("leo", "session-a")

    get_embeddings.assert_awaited_once_with(
        ["My favorite color is green\nassistant response"]
    )
    stored_turns = orchestrator.episodic_memory.append.await_args.args[0]
    assert len(stored_turns) == 1
    assert stored_turns[0].subject_id == "leo"
    assert stored_turns[0].session_id == "session-a"
    assert stored_turns[0].seq == 0
    assert stored_turns[0].embedding == [0.0] * 1536
    orchestrator.fact_memory.store_in_memory.assert_awaited_once_with(
        "leo", original_turns
    )
    orchestrator.summary_memory.store_in_memory.assert_awaited_once_with(
        "leo", original_turns
    )
    consolidated = orchestrator.working_memory.store_in_memory.await_args.args[1]
    assert consolidated.turns == []
    assert consolidated.status == "consolidated"
    orchestrator.working_memory.delete_from_memory.assert_not_awaited()

    orchestrator.fact_memory.retrieve_from_memory.return_value = "Favorite color: green"
    orchestrator.summary_memory.retrieve_from_memory.return_value = "Prior conversation"
    orchestrator.llm.generate_response.return_value = "Welcome back"

    await orchestrator.handle_incoming_message("leo", "session-b", "Hello again")

    context = orchestrator.llm.generate_response.call_args.args[0][1]["content"]
    assert "Favorite color: green" in context
    assert "Prior conversation" in context
    assert "## en curso" not in context


@pytest.mark.asyncio
async def test_naive_mode_answers_without_going_through_build_context(
    orchestrator, mocker
):
    """LEO-28 needs this arm untouched: no budget, no assembler, full history."""
    assemble = mocker.patch(
        "app.services.memory.cognitive_orchestrator.assemble", new_callable=AsyncMock
    )
    orchestrator.naive = True
    orchestrator.episodic_memory.history.return_value = [turn("archived message")]
    orchestrator.working_memory.retrieve_from_memory.return_value = session()
    orchestrator.llm.generate_response.return_value = "Hello!"

    reply, context = await orchestrator.handle_incoming_message(
        "leo", "session-id", "Test input"
    )

    assert reply == "Hello!"
    assert context is None
    assemble.assert_not_awaited()
    prompt = orchestrator.llm.generate_response.call_args.args[0][1]["content"]
    assert "archived message" in prompt
