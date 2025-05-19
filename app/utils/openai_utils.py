import os

from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def get_embedding(text: str) -> list[float]:
    """Obtiene el embedding vectorial de un texto utilizando el modelo 'text-embedding-3-small'.

    Args:
        text (str): El texto a procesar.

    Returns:
        list[float]: Lista de valores float que representan el embedding del texto.
    """
    response = await client.embeddings.create(
        model="text-embedding-3-small", input=text
    )
    return response.data[0].embedding
