import json
from typing import List

from app.prompts.filters import FILTER_EXTRACTION_PROMPT
from app.services.llm.openai_client import OpenAIClient
from app.utils.openai_utils import get_embedding
from app.services.storage.search_engine_storage import SearchEngineStorage

async def perform_vehicle_search(query: str, k:int = 5) -> List[dict]:
    print("Entrando al try")
    search_engine_storage = SearchEngineStorage()
    print("Se declaró search_engine_storage")
    # Paso 1: Obtener filtros desde el LLM
    print(f"query {query}")
    prompt = FILTER_EXTRACTION_PROMPT.format(query=query)
    print(f"prompt {prompt}")
    openai_client = OpenAIClient()
    messages = [{"role": "user", "content": prompt}]
    response = await openai_client.generate_response(messages)
    filters = json.loads(response)
    
    print(f"filters {filters}")

    # Paso 2: Obtener vector del query
    vector = await get_embedding(query)

    # Paso 3: Realizar búsqueda con filtros
    results = await search_engine_storage.knn_search(vector, k=k, filters=filters)
    return results