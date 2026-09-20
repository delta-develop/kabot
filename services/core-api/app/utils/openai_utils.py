from app.services.storage.connections import get_openai_client

MAX_EMBEDDING_INPUT_BYTES = 8192
EMBEDDING_BATCH_SIZE = 36


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
