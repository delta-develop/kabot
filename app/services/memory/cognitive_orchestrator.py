import json
from typing import Any, Dict, List

from app.prompts.conversation import build_intention_prompt_messages
from app.prompts.exit import EXIT_PROMPT
from app.prompts.finance import FINANCE_PROMPT
from app.prompts.kavak import KAVAK_INFO_PROMPT
from app.prompts.summary import summarize_vehicle_results
from app.services.search.search_handler import perform_vehicle_search


class CognitiveOrchestrator:
    """
    Orchestrates the cognitive processes for handling user conversations,
    including managing different types of memory, interpreting user intentions,
    and generating appropriate responses using a language model.
    """
    def __init__(self):
        self.working_memory = None
        self.fact_memory = None
        self.episodic_memory = None
        self.summary_memory = None
        self.llm = None

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
        Handles an incoming message from the user, determines the intention, and generates an appropriate response.

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

        working_context = await self.working_memory.retrieve_from_memory(user_id) or []
        history_text = self._format_history(working_context)
        facts, summary = await self._load_fact_and_summary_context(user_id)
        prompt_messages = build_intention_prompt_messages(
            facts, summary, history_text.strip(), user_msg
        )
        llm_raw = await self.llm.generate_response(prompt_messages)
        try:
            parsed = json.loads(llm_raw)
            intention = parsed.get("intention", "none")
            llm_reply = parsed.get("response", "")
        except Exception:
            intention = "none"
            llm_reply = llm_raw
        if intention == "episodic_memory":
            llm_reply = await self._handle_episodic_memory_intention(user_id, user_msg)
        elif intention == "search":
            llm_reply = await self._handle_search_intention(user_id, user_msg)
        elif intention == "financing":
            llm_reply = await self._handle_financing_intention(
                user_id, user_msg, parsed
            )
        elif intention == "kavak_info":
            llm_reply = await self._handle_kavak_info_intention(user_id, user_msg)
        elif intention == "exit":
            llm_reply = await self._handle_exit_intention(user_id, user_msg)
        else:
            await self._store_dialogue(user_id, user_msg, llm_reply)
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
    async def from_defaults(cls) -> "CognitiveOrchestrator":
        from app.services.memory.working_memory import WorkingMemory
        from app.services.memory.fact_memory import FactMemory
        from app.services.memory.episodic_memory import EpisodicMemory
        from app.services.memory.summary_memory import SummaryMemory
        from app.services.llm.openai_client import OpenAIClient

        orchestrator = cls.__new__(cls)
        orchestrator.llm = OpenAIClient()
        orchestrator.working_memory = WorkingMemory()
        orchestrator.fact_memory = FactMemory(orchestrator.llm)
        orchestrator.episodic_memory = EpisodicMemory()
        orchestrator.summary_memory = SummaryMemory(orchestrator.llm)

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

    async def _handle_episodic_memory_intention(
        self, user_id: str, user_msg: str
    ) -> str:
        history = await self.expand_context_from_long_term(user_id)
        history_text = self._format_history(history)
        facts, summary = await self._load_fact_and_summary_context(user_id)
        context_with_history = [
            {
                "role": "system",
                "content": f"""
                    <context>
                        <fact_memory>{facts}</fact_memory>
                        <summary_memory>{summary}</summary_memory>
                        <history>
                        {history_text.strip()}
                        </history>
                    </context>
                """.strip(),
            }
        ]
        extended_messages = [
            build_intention_prompt_instruction(),
            *context_with_history,
            {"role": "user", "content": f"<user_input>{user_msg}</user_input>"},
        ]
        return await self.llm.generate_response(extended_messages)

    async def _handle_search_intention(self, user_id: str, user_msg: str) -> str:
        """
        Handles the 'search' intention by querying for vehicles, summarizing the results,
        and storing the interaction in memory.

        Args:
            user_id (str): The ID of the user.
            user_msg (str): The input message from the user.

        Returns:
            str: The assistant's summary response.
        """
        results = await perform_vehicle_search(user_msg, k=5)
        summary_prompt = await summarize_vehicle_results(results)
        llm_reply = await self.llm.generate_response(
            [{"role": "user", "content": summary_prompt}]
        )
        await self.working_memory.store_in_memory(
            user_id,
            [
                {"role": "user", "content": user_msg},
                {
                    "role": "assistant",
                    "content": f"<natural_language_summary>{llm_reply}</natural_language_summary>",
                },
                {
                    "role": "assistant",
                    "content": f"<vehicle_results>{json.dumps(results)}</vehicle_results>",
                },
            ],
        )
        return llm_reply

    async def _handle_financing_intention(
        self, user_id: str, user_msg: str, parsed: dict
    ) -> str:
        """
        Handles the 'financing' intention using provided vehicle data.

        Args:
            user_id (str): The ID of the user.
            user_msg (str): The user's message.
            parsed (dict): Parsed JSON response with vehicle data.

        Returns:
            str: LLM's response regarding financing options.
        """
        vehicle_data = parsed.get("vehicle_data", {})
        financing_prompt = FINANCE_PROMPT.format(
            user_input=user_msg, vehicle_data=vehicle_data
        )
        llm_reply = await self.llm.generate_response(
            [{"role": "user", "content": financing_prompt}]
        )
        await self._store_dialogue(user_id, user_msg, llm_reply)
        return llm_reply

    async def _handle_kavak_info_intention(self, user_id: str, user_msg: str) -> str:
        """
        Handles the 'kavak_info' intention by querying the Kavak prompt.

        Args:
            user_id (str): The ID of the user.
            user_msg (str): The user's input message.

        Returns:
            str: The assistant's Kavak-related response.
        """
        kavak_prompt = KAVAK_INFO_PROMPT.format(user_input=user_msg)
        llm_reply = await self.llm.generate_response(
            [{"role": "user", "content": kavak_prompt}]
        )
        await self._store_dialogue(user_id, user_msg, llm_reply)
        return llm_reply

    async def _handle_exit_intention(self, user_id: str, user_msg: str) -> str:
        """
        Handles the 'exit' intention by summarizing the conversation and persisting it to memory.

        Args:
            user_id (str): The ID of the user.
            user_msg (str): The user's final message.

        Returns:
            str: A final response from the assistant.
        """
        history = await self.working_memory.retrieve_from_memory(user_id) or []
        history_text = self._format_history(history)
        facts, summary = await self._load_fact_and_summary_context(user_id)
        prompt = EXIT_PROMPT.format(
            user_input=user_msg,
            working_memory=history_text.strip(),
            facts=facts,
            summary=summary,
        )
        llm_reply = await self.llm.generate_response(
            [{"role": "user", "content": prompt}]
        )
        await self._store_dialogue(user_id, user_msg, llm_reply)
        await self.persist_conversation_closure(user_id)
        return llm_reply
