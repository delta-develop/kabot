from app.services.memory.memory import Memory
from app.services.storage.non_relational_storage import NonRelationalStorage
from app.services.llm.base import LLMBase
from typing import Any, Optional
from app.prompts.facts import build_fact_merge_prompt
import json


class FactMemory(Memory):
    def __init__(self, llm: LLMBase):
        self.storage = NonRelationalStorage(collection_name="fact_memory")
        self.llm = llm

    async def store_in_memory(self, key: str, data: Any) -> None:
        old_facts = await self.retrieve_from_memory(key)
        prompt = await build_fact_merge_prompt(recent_messages=data, previous_facts=old_facts or {})
        raw = await self.llm.generate_response([prompt])
        updated_facts = json.loads(raw)
        await self.storage.save({
            "whatsapp_id": key,
            "data": updated_facts
        })

    async def retrieve_from_memory(self, key: str) -> Optional[Any]:
        doc = await self.storage.get({"whatsapp_id": key})
        return doc.get("facts") if doc else None

    async def delete_from_memory(self, key: str) -> None:
        await self.storage.delete(key)
