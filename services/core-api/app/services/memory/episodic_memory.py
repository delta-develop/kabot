from app.models.turn import Turn
from app.services.memory.memory import EpisodicLog
from app.services.storage.relational_storage import RelationalStorage


class EpisodicMemory(EpisodicLog):
    """Stores complete conversation turns in PostgreSQL."""

    def __init__(self) -> None:
        self.storage = RelationalStorage()

    async def append(self, turns: list[Turn]) -> None:
        await self.storage.save_many(turns)

    async def history(self, subject_id: str, limit: int | None = None) -> list[Turn]:
        return await self.storage.history(subject_id, limit)
