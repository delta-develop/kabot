from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel

from app.models.turn import Fragment, FragmentView
from app.services.memory.cognitive_orchestrator import CognitiveOrchestrator
from app.services.memory.episodic_memory import EpisodicMemory
from app.services.memory.working_memory import WorkingMemory
from app.utils.openai_utils import MAX_EMBEDDING_INPUT_BYTES, get_embedding

router = APIRouter(prefix="/subjects")


class FactsView(BaseModel):
    subject_id: str
    facts: dict | None


class SummaryView(BaseModel):
    subject_id: str
    summary: str | None


@router.get("/{subject_id}/recall", response_model=list[FragmentView])
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


@router.get("/{subject_id}/memory/facts", response_model=FactsView)
async def get_facts(subject_id: str) -> FactsView:
    orchestrator = await CognitiveOrchestrator.from_defaults()
    facts: Any = await orchestrator.fact_memory.retrieve_from_memory(subject_id)
    return FactsView(subject_id=subject_id, facts=facts)


@router.get("/{subject_id}/memory/summary", response_model=SummaryView)
async def get_summary(subject_id: str) -> SummaryView:
    orchestrator = await CognitiveOrchestrator.from_defaults()
    summary: Any = await orchestrator.summary_memory.retrieve_from_memory(subject_id)
    return SummaryView(subject_id=subject_id, summary=summary)


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(subject_id: str) -> Response:
    """Erases a subject from all four memory layers."""
    orchestrator = await CognitiveOrchestrator.from_defaults()
    await orchestrator.fact_memory.delete_from_memory(subject_id)
    await orchestrator.summary_memory.delete_from_memory(subject_id)
    await orchestrator.episodic_memory.delete(subject_id)
    await WorkingMemory().forget_subject(subject_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
