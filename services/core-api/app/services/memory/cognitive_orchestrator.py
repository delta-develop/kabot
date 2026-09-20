from typing import Any, Dict, List

from app.prompts.conversation import build_conversation_prompt


class CognitiveOrchestrator:
    """
    Orchestrates the cognitive processes for handling user conversations,
    including managing different types of memory and generating responses using a
    language model.
    """

    def __init__(self, naive: bool = False):
        self.working_memory: Any = None
        self.fact_memory: Any = None
        self.episodic_memory: Any = None
        self.summary_memory: Any = None
        self.llm: Any = None
        self.naive: bool = naive

    async def load_initial_context(self, user_id: str) -> List[Dict[str, str]]:
        """
        Loads summary and factual memory into context for LLM priming.

        Args:
            user_id (str): The ID of the user.

        Returns:
            List[Dict[str, str]]: The context messages to be used as system prompts.
        """
        context = []

        facts = await self.fact_memory.retrieve_from_memory(user_id)
        if facts:
            context.append(
                {
                    "role": "system",
                    "content": f"<context>Relevant facts: {str(facts)}</context>",
                }
            )

        summary = await self.summary_memory.retrieve_from_memory(user_id)
        if summary:
            context.append(
                {"role": "system", "content": f"<context>{summary}</context>"}
            )

        if context:
            context.insert(
                0,
                {
                    "role": "system",
                    "content": "The following context has been retrieved from memory to help you understand the user. Do not repeat it.",
                },
            )

        return context

    async def handle_conversation_start(self, user_id: str) -> List[Dict[str, str]]:
        """
        Loads user's summary and facts into working memory at the start of a conversation.

        Args:
            user_id (str): The ID of the user.

        Returns:
            List[Dict[str, str]]: Structured messages for initializing the conversation.
        """
        context = await self.load_initial_context(user_id)
        await self.working_memory.store_in_memory(user_id, context)
        return context

    async def handle_incoming_message(self, user_id: str, user_msg: str) -> str:
        """
        Handles an incoming message and generates an appropriate response.

        Args:
            user_id (str): The ID of the user.
            user_msg (str): The user's input message.

        Returns:
            str: The assistant's response.
        """
        context = await self.working_memory.retrieve_from_memory(user_id)
        if not context:
            context = await self.load_initial_context(user_id)
            await self.working_memory.store_in_memory(user_id, context)

        if self.naive:
            history_context = await self.expand_context_from_long_term(user_id)
            history_text = self._format_history(history_context)
            facts, summary = "", ""
        else:
            working_context = (
                await self.working_memory.retrieve_from_memory(user_id) or []
            )
            history_text = self._format_history(working_context)
            facts, summary = await self._load_fact_and_summary_context(user_id)

        prompt_messages = build_conversation_prompt(
            facts, summary, history_text.strip(), user_msg
        )
        llm_reply = await self.llm.generate_response(prompt_messages)

        await self._store_dialogue(user_id, user_msg, llm_reply)

        if not llm_reply.strip():
            llm_reply = "Sorry, I don't have an answer for that right now."
        return llm_reply

    async def _load_fact_and_summary_context(self, user_id: str) -> tuple[str, str]:
        facts = await self.fact_memory.retrieve_from_memory(user_id) or ""
        summary = await self.summary_memory.retrieve_from_memory(user_id) or ""
        return facts, summary

    def _format_history(self, messages: List[Dict[str, str]]) -> str:
        """
        Formats a list of messages as XML blocks for the prompt.

        Args:
            messages (List[Dict[str, str]]): List of message dicts with 'role' and 'content'.

        Returns:
            str: Formatted history string.
        """
        history_text = ""
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            history_text += f"<{role}>{content}</{role}>\n"
        return history_text.strip()

    async def expand_context_from_long_term(self, user_id: str) -> List[Dict[str, str]]:
        """
        Retrieves full episodic memory for a user.

        Args:
            user_id (str): The ID of the user.

        Returns:
            List[Dict[str, str]]: The episodic memory entries.
        """
        return await self.episodic_memory.retrieve_from_memory(user_id) or []

    async def persist_conversation_closure(self, user_id: str) -> None:
        """
        Persists working memory into long-term storage and clears working memory.

        Args:
            user_id (str): The ID of the user.
        """
        data = await self.working_memory.retrieve_from_memory(user_id)
        if data:
            filtered = [msg for msg in data if msg.get("content")]
            await self.episodic_memory.store_in_memory(user_id, filtered)
            await self.summary_memory.store_in_memory(user_id, filtered)
            await self.fact_memory.store_in_memory(user_id, filtered)
            await self.working_memory.delete_from_memory(user_id)

    async def generate_and_merge_summary(self, user_id: str) -> None:
        """
        Generates a new summary and stores it in summary memory.

        Args:
            user_id (str): The ID of the user.
        """
        data = await self.working_memory.retrieve_from_memory(user_id)
        if data:
            await self.summary_memory.store_in_memory(user_id, {"data": data})

    async def extract_and_update_facts(self, user_id: str) -> None:
        """
        Extracts and updates fact memory from recent working memory.

        Args:
            user_id (str): The ID of the user.
        """
        data = await self.working_memory.retrieve_from_memory(user_id)
        if data:
            await self.fact_memory.store_in_memory(user_id, {"data": data})

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

    async def _store_dialogue(self, user_id: str, user_msg: str, assistant_msg: str):
        """
        Stores the user and assistant messages into working memory.

        Args:
            user_id (str): The ID of the user.
            user_msg (str): The message from the user.
            assistant_msg (str): The message generated by the assistant.
        """
        await self.working_memory.store_in_memory(
            user_id,
            [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": assistant_msg},
            ],
        )
