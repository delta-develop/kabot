from app.services.memory.memory import Memory
from app.services.storage.non_relational_storage import NonRelationalStorage
from app.services.llm.base import LLMBase
from typing import Any, Optional
from app.prompts.summary import build_summary_merge_prompt


class SummaryMemory(Memory):
    def __init__(self, llm: LLMBase):
        self.storage = NonRelationalStorage(collection_name="summary_memory")
        self.llm = llm

    async def store_in_memory(self, key: str, data: Any) -> None:
        old_summary = await self.retrieve_from_memory(key)
        prompt = await build_summary_merge_prompt(recent_messages=data, previous_summary=old_summary or "")
        merged_summary = await self.llm.generate_response([prompt])
        await self.storage.save({
            "whatsapp_id": key,
            "data": merged_summary
        })

    async def retrieve_from_memory(self, key: str) -> Optional[Any]:
        doc = await self.storage.get({"whatsapp_id": key})
        return doc.get("summary") if doc else None

    async def delete_from_memory(self, key: str) -> None:
        await self.storage.delete(key)
