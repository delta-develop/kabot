from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.models.context import Context
from app.models.session import SessionDocument, TurnDraft
from app.models.turn import TurnView
from app.services.memory.cognitive_orchestrator import CognitiveOrchestrator
from app.services.memory.context_builder import (
    DEFAULT_CONTEXT_BUDGET,
    MIN_CONTEXT_BUDGET,
)
from app.services.memory.episodic_memory import EpisodicMemory
from app.services.memory.working_memory import WorkingMemory
from app.services.storage.consolidation_stream import enqueue
from app.utils.openai_utils import MAX_EMBEDDING_INPUT_BYTES

MAX_MESSAGE_LENGTH = 4000

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


class WorkingMemoryView(BaseModel):
    session_id: str
    subject_id: str
    status: str
    turns: list[TurnDraft]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    budget: int | None = None


class ChatReply(BaseModel):
    reply: str
    context: Context | None


def _validate_budget(budget: int) -> int:
    if budget < MIN_CONTEXT_BUDGET:
        raise HTTPException(
            status_code=400,
            detail=(
                f"budget must be at least {MIN_CONTEXT_BUDGET} tokens; "
                f"{budget} cannot hold any memory layer"
            ),
        )
    return budget


def _validate_query(text: str) -> str:
    if len(text.encode("utf-8")) > MAX_EMBEDDING_INPUT_BYTES:
        raise HTTPException(
            status_code=422,
            detail="Query must be at most 8,192 UTF-8 bytes",
        )
    return text


async def _load_session(session_id: str) -> SessionDocument:
    session = await WorkingMemory().retrieve_from_memory(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("", response_model=SessionCreated)
async def create_session(request: SessionCreate) -> SessionCreated:
    session_id = str(uuid4())
    now = datetime.now(UTC)
    session = SessionDocument(
        subject_id=request.subject_id, turns=[], last_activity=now
    )
    working_memory = WorkingMemory()
    await working_memory.store_in_memory(session_id, session)
    await working_memory.track_session(request.subject_id, session_id)
    return SessionCreated(session_id=session_id)


@router.get("/{session_id}", response_model=SessionStatus)
async def get_session(session_id: str) -> SessionStatus:
    session = await _load_session(session_id)
    return SessionStatus(
        session_id=session_id,
        subject_id=session.subject_id,
        status=session.status,
        turn_count=len(session.turns),
    )


@router.get("/{session_id}/context", response_model=Context)
async def get_context(
    session_id: str,
    q: Annotated[str, Query(min_length=1, max_length=MAX_MESSAGE_LENGTH)],
    budget: Annotated[int, Query()] = DEFAULT_CONTEXT_BUDGET,
) -> Context:
    _validate_budget(budget)
    _validate_query(q)
    session = await _load_session(session_id)
    orchestrator = await CognitiveOrchestrator.from_defaults()
    return await orchestrator.build_context(session_id, session, q, budget)


@router.post("/{session_id}/chat", response_model=ChatReply)
async def chat(
    session_id: str,
    request: ChatRequest,
    naive: Annotated[bool, Query()] = False,
) -> ChatReply:
    budget = _validate_budget(
        request.budget if request.budget is not None else DEFAULT_CONTEXT_BUDGET
    )
    _validate_query(request.message)
    session = await _load_session(session_id)
    if session.status != "open":
        # Writing here would resurrect the session: seq restarts at zero while
        # the turns it already had live in Postgres under the same session_id.
        raise HTTPException(
            status_code=409,
            detail=f"Session is {session.status}; open a new session to keep talking",
        )
    orchestrator = await CognitiveOrchestrator.from_defaults(naive=naive)
    reply, context = await orchestrator.handle_incoming_message(
        session.subject_id, session_id, request.message, budget
    )
    return ChatReply(reply=reply, context=context)


@router.get("/{session_id}/memory/working", response_model=WorkingMemoryView)
async def get_working_memory(session_id: str) -> WorkingMemoryView:
    session = await _load_session(session_id)
    return WorkingMemoryView(
        session_id=session_id,
        subject_id=session.subject_id,
        status=session.status,
        turns=session.turns,
    )


@router.get("/{session_id}/turns", response_model=list[TurnView])
async def get_session_turns(
    session_id: str,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TurnView]:
    turns = await EpisodicMemory().by_session(session_id, limit, offset)
    return [TurnView.model_validate(turn, from_attributes=True) for turn in turns]


@router.post("/{session_id}/close", status_code=status.HTTP_202_ACCEPTED)
async def close_session(session_id: str) -> dict[str, str]:
    """Queues the session for consolidation and returns immediately.

    The work happens in the consolidation worker, so this handler touches Redis
    and nothing else.
    """
    working_memory = WorkingMemory()
    session = await working_memory.retrieve_from_memory(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "open":
        raise HTTPException(status_code=409, detail=f"Session is {session.status}")

    # Queued before the status is written: a session in the stream still
    # consolidates if this process dies here, while a session marked
    # `consolidating` with nothing queued is the hole LEO-24 left open.
    await enqueue(session_id)
    session.status = "consolidating"
    await working_memory.store_in_memory(session_id, session)
    return {"status": "consolidating"}
