from openai import AsyncOpenAI
import os

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def get_embedding(text: str) -> list[float]:
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding
