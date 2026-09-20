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


def test_expected_routes_are_registered():
    expected_routes = {
        ("POST", "/sessions"),
        ("GET", "/sessions/{session_id}"),
        ("POST", "/sessions/{session_id}/close"),
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
