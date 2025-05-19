from typing import Any

from app.prompts.summary import build_summary_merge_prompt
from app.services.llm.base import LLMBase
from app.services.memory.memory import Memory
from app.services.storage.non_relational_storage import NonRelationalStorage


class SummaryMemory(Memory):
    """Handles storing and retrieving summarized conversational memory."""

    def __init__(self, llm: LLMBase):
        """Initializes the SummaryMemory with a language model and storage."""
        self.storage = NonRelationalStorage(collection_name="summary_memory")
        self.llm = llm

    async def store_in_memory(self, key: str, data: Any) -> None:
        """Stores a merged summary in memory for a given user key.

        Args:
            key: The user identifier (e.g. WhatsApp ID).
            data: The recent conversation messages to summarize.
        """
        old_summary = await self.retrieve_from_memory(key)
        prompt = await build_summary_merge_prompt(
            recent_messages=data, previous_summary=old_summary or ""
        )
        merged_summary = await self.llm.generate_response([prompt])
        await self.storage.save({"whatsapp_id": key, "data": merged_summary[0]})

    async def retrieve_from_memory(self, key: str) -> Any:
        """Retrieves the summarized memory for a given user key.

        Args:
            key: The user identifier.

        Returns:
            The summary string if found, otherwise None.
        """
        doc = await self.storage.get({"whatsapp_id": key})
        return doc.get("summary") if doc else None

    async def delete_from_memory(self, key: str) -> None:
        """Deletes the summarized memory for a given user key.

        Args:
            key: The user identifier.
        """
        await self.storage.delete(key)
