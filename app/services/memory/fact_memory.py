from typing import Any

import json

from app.prompts.facts import build_fact_merge_prompt
from app.services.llm.base import LLMBase
from app.services.memory.memory import Memory
from app.services.storage.non_relational_storage import NonRelationalStorage


class FactMemory(Memory):
    """Handles long-term factual memory storage using a non-relational database and an LLM for merging.

    Attributes:
        storage (NonRelationalStorage): Storage interface for fact memory.
        llm (LLMBase): Large language model used for merging facts.
    """

    def __init__(self, llm: LLMBase):
        """Initializes FactMemory with a given LLM and connects to the non-relational storage.

        Args:
            llm (LLMBase): The large language model used to merge factual data.
        """
        self.storage = NonRelationalStorage(collection_name="fact_memory")
        self.llm = llm

    async def store_in_memory(self, key: str, data: Any) -> None:
        """Stores or updates factual memory for a given key by merging new data with existing memory.

        Args:
            key (str): Identifier, typically a user ID.
            data (Any): Recent messages or facts to store.

        Returns:
            None
        """
        old_facts = await self.retrieve_from_memory(key)
        prompt = await build_fact_merge_prompt(
            recent_messages=data, previous_facts=old_facts or {}
        )
        raw = await self.llm.generate_response([prompt])
        updated_facts = json.loads(raw)
        await self.storage.save({"whatsapp_id": key, "data": updated_facts})

    async def retrieve_from_memory(self, key: str) -> Any:
        """Retrieves factual memory associated with the given key.

        Args:
            key (str): Identifier to retrieve stored facts.

        Returns:
            Any: The stored facts, if any; otherwise None.
        """
        doc = await self.storage.get({"whatsapp_id": key})
        return doc.get("facts") if doc else None

    async def delete_from_memory(self, key: str) -> None:
        """Deletes factual memory associated with the given key.

        Args:
            key (str): Identifier whose memory should be deleted.

        Returns:
            None
        """
        await self.storage.delete(key)
