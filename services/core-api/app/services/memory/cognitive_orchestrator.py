from datetime import UTC, datetime
from typing import Any, Sequence

from app.models.session import SessionDocument, TurnDraft
from app.models.turn import Turn
from app.prompts.conversation import build_conversation_prompt
from app.services.llm.base import LLMBase
from app.services.memory.memory import EpisodicLog, KeyedMemory
from app.utils.openai_utils import get_embeddings


class CognitiveOrchestrator:
    """Coordinates conversational responses and layered memory."""

    def __init__(self, naive: bool = False):
        self.working_memory: KeyedMemory[SessionDocument]
        self.fact_memory: KeyedMemory[Any]
        self.episodic_memory: EpisodicLog
        self.summary_memory: KeyedMemory[Any]
        self.llm: LLMBase
        self.naive: bool = naive

    async def handle_incoming_message(
        self, subject_id: str, session_id: str, user_msg: str
    ) -> str:
        """Generates a response using subject and session memory."""
        session = await self.working_memory.retrieve_from_memory(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")

        history: Sequence[TurnDraft | Turn]
        if self.naive:
            history = await self.expand_context_from_long_term(subject_id)
            facts, summary = "", ""
        else:
            history = session.turns
            facts, summary = await self._load_fact_and_summary_context(subject_id)

        prompt_messages = build_conversation_prompt(
            facts, summary, self._format_history(history), user_msg
        )
        llm_reply = await self.llm.generate_response(prompt_messages)
        if not llm_reply.strip():
            llm_reply = "Sorry, I don't have an answer for that right now."

        await self._store_dialogue(session_id, session, user_msg, llm_reply)
        return llm_reply

    async def _load_fact_and_summary_context(self, subject_id: str) -> tuple[Any, Any]:
        facts = await self.fact_memory.retrieve_from_memory(subject_id) or ""
        summary = await self.summary_memory.retrieve_from_memory(subject_id) or ""
        return facts, summary

    def _format_history(self, turns: Sequence[TurnDraft | Turn]) -> str:
        return "\n".join(
            f"<user>{turn.user_text}</user>"
            f"<assistant>{turn.assistant_text}</assistant>"
            for turn in turns
        )

    async def expand_context_from_long_term(self, subject_id: str) -> list[Turn]:
        return await self.episodic_memory.history(subject_id)

    async def persist_conversation_closure(
        self, subject_id: str, session_id: str
    ) -> None:
        session = await self.working_memory.retrieve_from_memory(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")

        if session.turns:
            embeddings = await get_embeddings(
                [f"{turn.user_text}\n{turn.assistant_text}" for turn in session.turns]
            )
            episodic_turns = [
                Turn(
                    subject_id=subject_id,
                    session_id=session_id,
                    **turn.model_dump(),
                    embedding=embedding,
                )
                for turn, embedding in zip(session.turns, embeddings, strict=True)
            ]
            await self.episodic_memory.append(episodic_turns)
            await self.summary_memory.store_in_memory(subject_id, session.turns)
            await self.fact_memory.store_in_memory(subject_id, session.turns)
        session.turns = []
        session.status = "consolidated"
        await self.working_memory.store_in_memory(session_id, session)

    async def generate_and_merge_summary(
        self, subject_id: str, session_id: str
    ) -> None:
        session = await self.working_memory.retrieve_from_memory(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")
        if session.turns:
            await self.summary_memory.store_in_memory(subject_id, session.turns)

    async def extract_and_update_facts(self, subject_id: str, session_id: str) -> None:
        session = await self.working_memory.retrieve_from_memory(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")
        if session.turns:
            await self.fact_memory.store_in_memory(subject_id, session.turns)

    @classmethod
    async def from_defaults(cls, naive: bool = False) -> "CognitiveOrchestrator":
        from app.services.llm.openai_client import OpenAIClient
        from app.services.memory.episodic_memory import EpisodicMemory
        from app.services.memory.fact_memory import FactMemory
        from app.services.memory.summary_memory import SummaryMemory
        from app.services.memory.working_memory import WorkingMemory

        orchestrator = cls.__new__(cls)
        orchestrator.llm = OpenAIClient()
        orchestrator.working_memory = WorkingMemory()
        orchestrator.fact_memory = FactMemory(orchestrator.llm)
        orchestrator.episodic_memory = EpisodicMemory()
        orchestrator.summary_memory = SummaryMemory(orchestrator.llm)
        orchestrator.naive = naive
        return orchestrator

    async def _store_dialogue(
        self,
        session_id: str,
        session: SessionDocument,
        user_msg: str,
        assistant_msg: str,
    ) -> None:
        now = datetime.now(UTC)
        session.turns.append(
            TurnDraft(
                seq=len(session.turns),
                ts=now,
                user_text=user_msg,
                assistant_text=assistant_msg,
            )
        )
        session.last_activity = now
        await self.working_memory.store_in_memory(session_id, session)
