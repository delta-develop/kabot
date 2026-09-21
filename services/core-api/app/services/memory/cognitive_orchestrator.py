from datetime import UTC, datetime
from typing import Any, Sequence

from app.models.context import Context, ContextBlock
from app.models.session import SessionDocument, TurnDraft
from app.models.turn import Turn
from app.prompts.conversation import (
    build_conversation_prompt,
    render_turn,
    scaffolding_tokens,
)
from app.services.llm.base import LLMBase
from app.services.memory.context_builder import (
    DEFAULT_CONTEXT_BUDGET,
    WORKING_HEADER,
    assemble,
)
from app.services.memory.memory import EpisodicLog, KeyedMemory
from app.utils.openai_utils import get_embeddings
from app.utils.token_utils import count_tokens


class CognitiveOrchestrator:
    """Coordinates conversational responses and layered memory."""

    def __init__(self, naive: bool = False):
        self.working_memory: KeyedMemory[SessionDocument]
        self.fact_memory: KeyedMemory[Any]
        self.episodic_memory: EpisodicLog
        self.summary_memory: KeyedMemory[Any]
        self.llm: LLMBase
        self.naive: bool = naive

    async def build_context(
        self, session_id: str, session: SessionDocument, q: str, budget: int
    ) -> Context:
        """Assembles the best context that fits in `budget` tokens."""
        return await assemble(
            session_id,
            session,
            q,
            budget,
            self.fact_memory,
            self.summary_memory,
            self.episodic_memory,
        )

    async def handle_incoming_message(
        self,
        subject_id: str,
        session_id: str,
        user_msg: str,
        budget: int = DEFAULT_CONTEXT_BUDGET,
    ) -> tuple[str, Context | None]:
        """Generates a response using subject and session memory.

        Returns the reply and the context it was grounded on. Naive mode has no
        budget to report, so it returns None.
        """
        session = await self.working_memory.retrieve_from_memory(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")

        if self.naive:
            history = await self.expand_context_from_long_term(subject_id)
            context, reported = self._naive_context(history), None
        else:
            context = await self.build_context(session_id, session, user_msg, budget)
            reported = context

        prompt_messages = build_conversation_prompt(context, user_msg)
        llm_reply = await self.llm.generate_response(prompt_messages)
        if not llm_reply.strip():
            llm_reply = "Sorry, I don't have an answer for that right now."

        await self._store_dialogue(session_id, session, user_msg, llm_reply)
        return llm_reply, reported

    def _naive_context(self, history: Sequence[TurnDraft | Turn]) -> Context:
        """Renders the whole episodic history, with no ceiling.

        LEO-28 needs this arm as its control, so the prompt it produces stays
        what it was: full history, no facts and no summary. `budget` is zero
        because naive never asked for one; this context is fed to the prompt
        builder and never returned over HTTP.
        """
        content = WORKING_HEADER + "".join(render_turn(turn) for turn in history)
        blocks = [
            ContextBlock(
                source="working", tokens=count_tokens(content), content=content
            )
        ]
        return Context(
            budget=0,
            used=sum(block.tokens for block in blocks),
            system_tokens=scaffolding_tokens(),
            message_tokens=0,
            blocks=blocks,
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
            # ponytail: only the turn log is idempotent, through UNIQUE
            # (session_id, seq). A retry that dies past the append re-merges the
            # same turns into the summary and the facts, so a twice-consolidated
            # session can end up with a summary that states the same thing
            # twice: degraded, never corrupted, and no turn is lost. The way out
            # is a per-step marker in Redis keyed by session, left unbuilt
            # because it is new state to maintain for a case expected never to
            # happen.
            await self.summary_memory.store_in_memory(subject_id, session.turns)
            await self.fact_memory.store_in_memory(subject_id, session.turns)
        # Working memory is cleared last: it is the source, and clearing it
        # before the summary lands would lose the conversation on a failure.
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
