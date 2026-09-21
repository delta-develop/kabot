import os

from app.services.storage.connections import get_openai_client

MAX_EMBEDDING_INPUT_BYTES = 8192
EMBEDDING_BATCH_SIZE = 36

# The gpt-5 line rejects `temperature` and prices cached input at a 90% discount,
# which is the shape of this workload: one system prompt and one set of facts
# repeated across every turn of a session.
DEFAULT_CHAT_MODEL = "gpt-5.6-luna"


def get_chat_model() -> str:
    """Return the configured chat model, or the default when none is set."""
    return os.getenv("OPENAI_MODEL") or DEFAULT_CHAT_MODEL


def get_reasoning_effort() -> str:
    """Return the reasoning effort to request, or an empty string to omit it.

    Reasoning tokens bill as output, so this path asks for none by default.
    A model that does not accept the parameter at all — gpt-4o, for instance —
    needs this set to an empty string.
    """
    return os.getenv("OPENAI_REASONING_EFFORT", "none")


async def get_embeddings(texts: list[str]) -> list[list[float]]:
    if any(len(text.encode("utf-8")) > MAX_EMBEDDING_INPUT_BYTES for text in texts):
        raise ValueError("Each embedding input must be at most 8,192 UTF-8 bytes")

    client = await get_openai_client()
    embeddings: list[list[float]] = []
    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        response = await client.embeddings.create(
            input=texts[start : start + EMBEDDING_BATCH_SIZE],
            model="text-embedding-3-small",
        )
        embeddings.extend(item.embedding for item in response.data)
    return embeddings


async def get_embedding(text: str) -> list[float]:
    return (await get_embeddings([text]))[0]
