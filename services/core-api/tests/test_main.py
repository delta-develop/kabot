from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

from fastapi.routing import iter_route_contexts
from fastapi.testclient import TestClient

from app.main import app
from app.models.session import SessionDocument


def test_expected_routes_are_registered():
    expected_routes = {
        ("POST", "/sessions"),
        ("POST", "/sessions/{session_id}/close"),
        ("GET", "/author"),
    }
    registered_routes = {
        (method, route.path)
        for route in iter_route_contexts(app.routes)
        for method in route.methods or ()
    }

    assert expected_routes <= registered_routes


def test_create_session_stores_empty_document(mocker):
    working_memory = AsyncMock()
    mocker.patch("app.api.routes.sessions.WorkingMemory", return_value=working_memory)

    response = TestClient(app).post("/sessions", json={"subject_id": "leo"})

    assert response.status_code == 200
    session_id = response.json()["session_id"]
    UUID(session_id)
    stored = working_memory.store_in_memory.call_args.args[1]
    assert stored.subject_id == "leo"
    assert stored.turns == []
    working_memory.store_in_memory.assert_awaited_once_with(session_id, stored)


def test_close_session_returns_accepted(mocker):
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
    orchestrator.persist_conversation_closure.assert_awaited_once_with(
        "leo", "session-id"
    )


def test_close_missing_session_returns_not_found(mocker):
    orchestrator = AsyncMock()
    orchestrator.working_memory.retrieve_from_memory.return_value = None
    mocker.patch(
        "app.api.routes.sessions.CognitiveOrchestrator.from_defaults",
        return_value=orchestrator,
    )

    response = TestClient(app).post("/sessions/missing/close")

    assert response.status_code == 404


def test_lifespan_creates_the_relational_schema(mocker):
    # Driven through the real ASGI lifespan protocol (not by calling the
    # `lifespan` function directly) so this fails if `app` is ever built
    # without `lifespan=lifespan` attached.
    setup = mocker.patch(
        "app.main.RelationalStorage.setup",
        new_callable=mocker.AsyncMock,
    )

    with TestClient(app):
        pass

    setup.assert_awaited_once()
