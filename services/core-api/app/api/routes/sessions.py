from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.models.session import SessionDocument
from app.services.memory.cognitive_orchestrator import CognitiveOrchestrator
from app.services.memory.working_memory import WorkingMemory

router = APIRouter(prefix="/sessions")


class SessionCreate(BaseModel):
    subject_id: str


class SessionCreated(BaseModel):
    session_id: str


@router.post("", response_model=SessionCreated)
async def create_session(request: SessionCreate) -> SessionCreated:
    session_id = str(uuid4())
    now = datetime.now(UTC)
    session = SessionDocument(
        subject_id=request.subject_id, turns=[], last_activity=now
    )
    await WorkingMemory().store_in_memory(session_id, session)
    return SessionCreated(session_id=session_id)


@router.post("/{session_id}/close", status_code=status.HTTP_202_ACCEPTED)
async def close_session(session_id: str) -> None:
    orchestrator = await CognitiveOrchestrator.from_defaults()
    session = await orchestrator.working_memory.retrieve_from_memory(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # ponytail: consolidate inline until LEO-27 replaces this call with a Redis Stream.
    try:
        await orchestrator.persist_conversation_closure(session.subject_id, session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
