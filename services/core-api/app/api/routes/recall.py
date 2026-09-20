from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.models.turn import Fragment
from app.services.memory.episodic_memory import EpisodicMemory
from app.utils.openai_utils import MAX_EMBEDDING_INPUT_BYTES, get_embedding

router = APIRouter(prefix="/subjects")


class RecallTurn(BaseModel):
    seq: int
    ts: datetime
    user_text: str
    assistant_text: str


class RecallFragment(BaseModel):
    turns: list[RecallTurn]
    session_id: str
    ts: datetime
    similarity: float


@router.get("/{subject_id}/recall", response_model=list[RecallFragment])
async def recall(
    subject_id: str,
    q: Annotated[str, Query(min_length=1)],
    k: Annotated[int, Query(ge=1, le=100)] = 5,
) -> list[Fragment]:
    if len(q.encode("utf-8")) > MAX_EMBEDDING_INPUT_BYTES:
        raise HTTPException(
            status_code=422,
            detail="Query must be at most 8,192 UTF-8 bytes",
        )
    memory = EpisodicMemory()
    if not await memory.has_turns(subject_id):
        return []
    vector = await get_embedding(q)
    return await memory.similar(subject_id, vector, k)
