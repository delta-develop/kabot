"""Módulo para manejar la intención de financiamiento utilizando un modelo LLM."""

from app.prompts.finance import FINANCE_PROMPT
from app.services.llm.openai_client import OpenAIClient

llm = OpenAIClient()


async def handle_financing_intent(user_query: str) -> str:
    """Procesa la intención de financiamiento usando un modelo LLM.

    Args:
        user_query (str): La consulta del usuario relacionada con financiamiento.

    Returns:
        str: La respuesta generada por el modelo LLM.
    """
    messages = [
        {"role": "system", "content": FINANCE_PROMPT},
        {"role": "user", "content": user_query},
    ]
    return await llm.generate_response(messages)
