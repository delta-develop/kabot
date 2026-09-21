from app.models.turn import Fragment, Turn
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

    async def has_turns(
        self, subject_id: str, exclude_session: str | None = None
    ) -> bool:
        return await self.storage.has_turns(subject_id, exclude_session)

    async def by_session(
        self, session_id: str, limit: int, offset: int = 0
    ) -> list[Turn]:
        return await self.storage.by_session(session_id, limit, offset)

    async def delete(self, subject_id: str) -> None:
        await self.storage.delete(subject_id)

    async def similar(
        self,
        subject_id: str,
        vector: list[float],
        k: int,
        exclude_session: str | None = None,
    ) -> list[Fragment]:
        return await self.storage.similar(subject_id, vector, k, exclude_session)
