from app.services.llm.openai_client import OpenAIClient
from app.prompts.finance import FINANCE_PROMPT

llm = OpenAIClient()

async def handle_financing_intent(user_query: str) -> str:
    messages = [
        {"role": "system", "content": FINANCE_PROMPT},
        {"role": "user", "content": user_query}
    ]
    return await llm.generate_response(messages)