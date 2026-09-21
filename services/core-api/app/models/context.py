from datetime import datetime
from typing import Literal

from pydantic import BaseModel

BlockSource = Literal["facts", "summary", "recall", "working"]


class FragmentRef(BaseModel):
    """Provenance of one recalled fragment, without its turns' embeddings."""

    session_id: str
    ts: datetime
    similarity: float
    usefulness: float | None = None
    seqs: list[int]


class ContextBlock(BaseModel):
    """One memory layer as it is rendered into the prompt.

    `content` is the exact string that reaches the model, and `tokens` counts
    that same string. Block contents always end with a newline, which is what
    makes the per-block counts add up to `Context.used`.
    """

    source: BlockSource
    tokens: int
    content: str
    fragments: list[FragmentRef] | None = None


class Context(BaseModel):
    """The best context that fits in `budget` tokens.

    `used` never exceeds `budget`, and equals the token count of every block
    content concatenated. `system_tokens` and `message_tokens` sit outside the
    budget and are reported so a caller can size the real prompt.
    """

    budget: int
    used: int
    system_tokens: int
    message_tokens: int
    blocks: list[ContextBlock]
