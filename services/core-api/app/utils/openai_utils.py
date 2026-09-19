from openai import AsyncOpenAI
from app.services.storage.connections import get_openai_client
from typing import List

async def get_embedding(text: str) -> List[float]:
    client = await get_openai_client()
    response = await client.embeddings.create(input=[text], model="text-embedding-3-small")
    return response.data[0].embedding