from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import BackgroundTasks, HTTPException
from fastapi.routing import iter_route_contexts
from fastapi.testclient import TestClient

from app.api.routes.sessions import close_session, get_session
from app.main import app
from app.models.session import SessionDocument
from app.models.turn import Fragment, Turn
from app.utils.openai_utils import MAX_EMBEDDING_INPUT_BYTES


def test_expected_routes_are_registered():
    expected_routes = {
        ("POST", "/sessions"),
        ("GET", "/sessions/{session_id}"),
        ("POST", "/sessions/{session_id}/close"),
        ("GET", "/subjects/{subject_id}/recall"),
        ("GET", "/author"),
    }
    registered_routes = {
        (method, route.path)
        for route in iter_route_contexts(app.routes)
        for method in route.methods or ()
    }

    assert expected_routes <= registered_routes


def test_create_session_stores_open_document(mocker):
    working_memory = AsyncMock()
    mocker.patch("app.api.routes.sessions.WorkingMemory", return_value=working_memory)

    response = TestClient(app).post("/sessions", json={"subject_id": "leo"})

    assert response.status_code == 200
    session_id = response.json()["session_id"]
    UUID(session_id)
    stored = working_memory.store_in_memory.call_args.args[1]
    assert stored.subject_id == "leo"
    assert stored.turns == []
    assert stored.status == "open"
    working_memory.store_in_memory.assert_awaited_once_with(session_id, stored)


@pytest.mark.asyncio
async def test_close_queues_consolidation_and_exposes_status_lifecycle(mocker):
    session = SessionDocument(
        subject_id="leo",
        turns=[],
        last_activity=datetime.now(UTC),
    )
    stored_session = session
    working_memory = AsyncMock()

    async def retrieve(_):
        return stored_session

    async def store(_, value):
        nonlocal stored_session
        stored_session = value.model_copy(deep=True)

    working_memory.retrieve_from_memory.side_effect = retrieve
    working_memory.store_in_memory.side_effect = store
    orchestrator = AsyncMock()
    orchestrator.working_memory = working_memory

    async def consolidate(_, session_id):
        current = await working_memory.retrieve_from_memory(session_id)
        current.status = "consolidated"
        await working_memory.store_in_memory(session_id, current)

    orchestrator.persist_conversation_closure.side_effect = consolidate
    mocker.patch(
        "app.api.routes.sessions.CognitiveOrchestrator.from_defaults",
        return_value=orchestrator,
    )
    mocker.patch("app.api.routes.sessions.WorkingMemory", return_value=working_memory)
    background = BackgroundTasks()

    response = await close_session("session-id", background)

    assert response == {"status": "consolidating"}
    assert len(background.tasks) == 1
    assert background.tasks[0].func == orchestrator.persist_conversation_closure
    assert (await get_session("session-id")).status == "consolidating"

    await background()

    assert (await get_session("session-id")).status == "consolidated"
    orchestrator.persist_conversation_closure.assert_awaited_once_with(
        "leo", "session-id"
    )


def test_close_returns_accepted(mocker):
    session = SessionDocument(
        subject_id="leo", turns=[], last_activity=datetime.now(UTC)
    )
    orchestrator = AsyncMock()
    orchestrator.working_memory.retrieve_from_memory.return_value = session
    mocker.patch(
        "app.api.routes.sessions.CognitiveOrchestrator.from_defaults",
        return_value=orchestrator,
    )

    response = TestClient(app).post("/sessions/session-id/close")

    assert response.status_code == 202
    assert response.json() == {"status": "consolidating"}


@pytest.mark.parametrize("session_status", ["consolidating", "consolidated"])
@pytest.mark.asyncio
async def test_repeat_close_returns_conflict_without_side_effects(
    mocker, session_status
):
    session = SessionDocument(
        subject_id="leo",
        turns=[],
        last_activity=datetime.now(UTC),
        status=session_status,
    )
    orchestrator = AsyncMock()
    orchestrator.working_memory.retrieve_from_memory.return_value = session
    mocker.patch(
        "app.api.routes.sessions.CognitiveOrchestrator.from_defaults",
        return_value=orchestrator,
    )
    background = BackgroundTasks()

    with pytest.raises(HTTPException) as error:
        await close_session("session-id", background)

    assert error.value.status_code == 409
    assert error.value.detail == f"Session is {session_status}"
    orchestrator.working_memory.store_in_memory.assert_not_awaited()
    assert background.tasks == []


def test_get_session_reports_status_and_turn_count(mocker):
    session = SessionDocument(
        subject_id="leo",
        turns=[],
        last_activity=datetime.now(UTC),
        status="consolidated",
    )
    working_memory = AsyncMock()
    working_memory.retrieve_from_memory.return_value = session
    mocker.patch("app.api.routes.sessions.WorkingMemory", return_value=working_memory)

    response = TestClient(app).get("/sessions/session-id")

    assert response.status_code == 200
    assert response.json() == {
        "session_id": "session-id",
        "subject_id": "leo",
        "status": "consolidated",
        "turn_count": 0,
    }


def test_missing_session_returns_not_found(mocker):
    orchestrator = AsyncMock()
    orchestrator.working_memory.retrieve_from_memory.return_value = None
    mocker.patch(
        "app.api.routes.sessions.CognitiveOrchestrator.from_defaults",
        return_value=orchestrator,
    )
    working_memory = AsyncMock()
    working_memory.retrieve_from_memory.return_value = None
    mocker.patch("app.api.routes.sessions.WorkingMemory", return_value=working_memory)

    assert TestClient(app).post("/sessions/missing/close").status_code == 404
    assert TestClient(app).get("/sessions/missing").status_code == 404


def test_lifespan_creates_the_relational_schema(mocker):
    setup = mocker.patch(
        "app.main.RelationalStorage.setup",
        new_callable=mocker.AsyncMock,
    )

    with TestClient(app):
        pass

    setup.assert_awaited_once()


def test_recall_without_history_skips_embedding(mocker):
    episodic_memory = AsyncMock()
    episodic_memory.has_turns.return_value = False
    mocker.patch("app.api.routes.recall.EpisodicMemory", return_value=episodic_memory)
    get_embedding = mocker.patch(
        "app.api.routes.recall.get_embedding", new_callable=AsyncMock
    )

    response = TestClient(app).get(
        "/subjects/leo/recall", params={"q": "where should I eat?"}
    )

    assert response.status_code == 200
    assert response.json() == []
    episodic_memory.has_turns.assert_awaited_once_with("leo")
    get_embedding.assert_not_awaited()
    episodic_memory.similar.assert_not_awaited()


def test_recall_embeds_query_once_and_omits_internal_turn_fields(mocker):
    first_ts = datetime(2026, 1, 1, tzinfo=UTC)
    second_ts = datetime(2026, 1, 2, tzinfo=UTC)
    first_turn = Turn(
        subject_id="leo",
        session_id="first-session",
        seq=14,
        ts=first_ts,
        user_text="Where did I eat?",
        assistant_text="Roma Norte",
        embedding=[1.0] + [0.0] * 1535,
    )
    second_turn = Turn(
        subject_id="leo",
        session_id="second-session",
        seq=3,
        ts=second_ts,
        user_text="Another memory",
        assistant_text="Another answer",
        embedding=[0.0, 1.0] + [0.0] * 1534,
    )
    fragments = [
        Fragment(
            turns=[first_turn],
            session_id="first-session",
            ts=first_ts,
            similarity=0.9,
        ),
        Fragment(
            turns=[second_turn],
            session_id="second-session",
            ts=second_ts,
            similarity=0.6,
        ),
    ]
    episodic_memory = AsyncMock()
    episodic_memory.has_turns.return_value = True
    episodic_memory.similar.return_value = fragments
    mocker.patch("app.api.routes.recall.EpisodicMemory", return_value=episodic_memory)
    vector = [0.5] * 1536
    get_embedding = mocker.patch(
        "app.api.routes.recall.get_embedding",
        AsyncMock(return_value=vector),
    )

    response = TestClient(app).get(
        "/subjects/leo/recall", params={"q": "where should I eat?"}
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "turns": [
                {
                    "seq": 14,
                    "ts": "2026-01-01T00:00:00Z",
                    "user_text": "Where did I eat?",
                    "assistant_text": "Roma Norte",
                }
            ],
            "session_id": "first-session",
            "ts": "2026-01-01T00:00:00Z",
            "similarity": 0.9,
        },
        {
            "turns": [
                {
                    "seq": 3,
                    "ts": "2026-01-02T00:00:00Z",
                    "user_text": "Another memory",
                    "assistant_text": "Another answer",
                }
            ],
            "session_id": "second-session",
            "ts": "2026-01-02T00:00:00Z",
            "similarity": 0.6,
        },
    ]
    episodic_memory.has_turns.assert_awaited_once_with("leo")
    get_embedding.assert_awaited_once_with("where should I eat?")
    episodic_memory.similar.assert_awaited_once_with("leo", vector, 5)


@pytest.mark.parametrize("k", [0, 101])
def test_recall_rejects_k_outside_http_contract(k):
    response = TestClient(app).get("/subjects/leo/recall", params={"q": "food", "k": k})

    assert response.status_code == 422


def test_recall_rejects_empty_query_before_memory_or_embedding(mocker):
    episodic_memory = AsyncMock()
    memory_factory = mocker.patch(
        "app.api.routes.recall.EpisodicMemory", return_value=episodic_memory
    )
    get_embedding = mocker.patch(
        "app.api.routes.recall.get_embedding", new_callable=AsyncMock
    )

    response = TestClient(app).get("/subjects/leo/recall", params={"q": ""})

    assert response.status_code == 422
    memory_factory.assert_not_called()
    get_embedding.assert_not_awaited()


def test_recall_rejects_oversized_multibyte_query_before_memory_or_embedding(mocker):
    episodic_memory = AsyncMock()
    memory_factory = mocker.patch(
        "app.api.routes.recall.EpisodicMemory", return_value=episodic_memory
    )
    get_embedding = mocker.patch(
        "app.api.routes.recall.get_embedding", new_callable=AsyncMock
    )
    oversized_query = "é" * (MAX_EMBEDDING_INPUT_BYTES // 2 + 1)

    response = TestClient(app).get(
        "/subjects/leo/recall", params={"q": oversized_query}
    )

    assert response.status_code == 422
    memory_factory.assert_not_called()
    get_embedding.assert_not_awaited()


def test_recall_accepts_query_at_exact_byte_limit(mocker):
    episodic_memory = AsyncMock()
    episodic_memory.has_turns.return_value = False
    memory_factory = mocker.patch(
        "app.api.routes.recall.EpisodicMemory", return_value=episodic_memory
    )
    get_embedding = mocker.patch(
        "app.api.routes.recall.get_embedding", new_callable=AsyncMock
    )
    maximum_query = "a" * MAX_EMBEDDING_INPUT_BYTES

    response = TestClient(app).get("/subjects/leo/recall", params={"q": maximum_query})

    assert response.status_code == 200
    assert response.json() == []
    memory_factory.assert_called_once_with()
    episodic_memory.has_turns.assert_awaited_once_with("leo")
    get_embedding.assert_not_awaited()
