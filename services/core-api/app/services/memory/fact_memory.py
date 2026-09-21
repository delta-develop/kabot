import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.prompts.facts import build_fact_merge_prompt
from app.services.llm.base import LLMBase
from app.services.memory.memory import KeyedMemory
from app.services.storage.non_relational_storage import NonRelationalStorage

logger = logging.getLogger(__name__)


class FactMemory(KeyedMemory[dict]):
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
        raw = await self.llm.generate_response([prompt], as_json=True)
        try:
            updated_facts = json.loads(raw)
        except json.JSONDecodeError:
            # The model owes us JSON and sometimes does not deliver. Facts merge
            # across sessions, so skipping one merge loses a little; raising here
            # would abort the whole closure and lose the summary too.
            logger.exception(
                "Fact merge returned malformed JSON for %s: %.200s", key, raw
            )
            return
        await self.storage.save(
            {
                "subject_id": key,
                "facts": updated_facts,
                "last_updated": datetime.now(UTC).isoformat(),
            }
        )

    async def retrieve_from_memory(self, key: str) -> dict | None:
        """Retrieves factual memory associated with the given key.

        Args:
            key (str): Identifier to retrieve stored facts.

        Returns:
            Any: The stored facts, if any; otherwise None.
        """
        doc = await self.storage.get({"subject_id": key})
        return doc.get("facts") if doc else None

    async def delete_from_memory(self, key: str) -> None:
        """Deletes factual memory associated with the given key.

        Args:
            key (str): Identifier whose memory should be deleted.

        Returns:
            None
        """
        await self.storage.delete(key)
