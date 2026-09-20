from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TurnDraft(BaseModel):
    """A complete exchange kept in working memory until consolidation."""

    seq: int
    ts: datetime
    user_text: str
    assistant_text: str


class SessionDocument(BaseModel):
    """The shape stored at session:{id} in Redis.

    This is the source of truth for LEO-23, LEO-24, and LEO-27. Changes to this
    shape require reviewing all three tickets.
    """

    subject_id: str
    turns: list[TurnDraft] = []
    last_activity: datetime
    status: Literal["open", "consolidating", "consolidated"] = "open"
