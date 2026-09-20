from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel

from app.models.session import SessionDocument
from app.services.memory.cognitive_orchestrator import CognitiveOrchestrator
from app.services.memory.working_memory import WorkingMemory

router = APIRouter(prefix="/sessions")


class SessionCreate(BaseModel):
    subject_id: str


class SessionCreated(BaseModel):
    session_id: str


class SessionStatus(BaseModel):
    session_id: str
    subject_id: str
    status: str
    turn_count: int


@router.post("", response_model=SessionCreated)
async def create_session(request: SessionCreate) -> SessionCreated:
    session_id = str(uuid4())
    now = datetime.now(UTC)
    session = SessionDocument(
        subject_id=request.subject_id, turns=[], last_activity=now
    )
    await WorkingMemory().store_in_memory(session_id, session)
    return SessionCreated(session_id=session_id)


@router.get("/{session_id}", response_model=SessionStatus)
async def get_session(session_id: str) -> SessionStatus:
    session = await WorkingMemory().retrieve_from_memory(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionStatus(
        session_id=session_id,
        subject_id=session.subject_id,
        status=session.status,
        turn_count=len(session.turns),
    )


@router.post("/{session_id}/close", status_code=status.HTTP_202_ACCEPTED)
async def close_session(session_id: str, background: BackgroundTasks) -> dict[str, str]:
    orchestrator = await CognitiveOrchestrator.from_defaults()
    session = await orchestrator.working_memory.retrieve_from_memory(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "open":
        raise HTTPException(status_code=409, detail=f"Session is {session.status}")

    session.status = "consolidating"
    await orchestrator.working_memory.store_in_memory(session_id, session)
    # ponytail: BackgroundTasks has no retry; LEO-27 replaces it with Redis Streams.
    background.add_task(
        orchestrator.persist_conversation_closure, session.subject_id, session_id
    )
    return {"status": "consolidating"}
