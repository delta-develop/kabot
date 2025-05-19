import json
from typing import List
from app.prompts.filters import FILTER_EXTRACTION_PROMPT
from app.services.llm.openai_client import OpenAIClient
from app.services.storage.search_engine_storage import SearchEngineStorage
from app.utils.openai_utils import get_embedding


async def perform_vehicle_search(query: str, k: int = 5) -> List[dict]:
    """Realiza una búsqueda de vehículos utilizando búsqueda vectorial y filtros extraídos por LLM.

    Args:
        query (str): Consulta en lenguaje natural del usuario.
        k (int, optional): Número de resultados a retornar. Por defecto es 5.

    Returns:
        List[dict]: Lista de vehículos que coinciden con la búsqueda y los filtros.
    """
    search_engine_storage = SearchEngineStorage()
    prompt = FILTER_EXTRACTION_PROMPT.format(query=query)
    openai_client = OpenAIClient()
    messages = [{"role": "user", "content": prompt}]
    response = await openai_client.generate_response(messages)
    filters = json.loads(response)
    vector = await get_embedding(query)
    results = await search_engine_storage.knn_search(vector, k=k, filters=filters)
    return results
