import os
from typing import Dict
from app.services.llm.base import LLMBase
import dotenv
from app.services.storage.connections import get_openai_client


dotenv.load_dotenv()


class OpenAIClient(LLMBase):
    """
    Asynchronous OpenAI client that implements the LLMBase interface
    for generating responses and interpreting input.
    """

    def __init__(self):
        self.model = os.getenv("OPENAI_MODEL")
        self.temperature = float(os.getenv("OPENAI_TEMPERATURE", 0.7))
        self.client = None
        
    async def get_client(self):
        if self.client is None:
            self.client = await get_openai_client()
        return self.client


    async def generate_response(self, messages: list) -> str:
        """
        Asynchronously generates a text response from a list of messages
        in OpenAI chat format.

        Args:
            messages (list): List of dictionaries representing a chat history.

        Returns:
            str: Text response from the language model.
        """
        if not self.client:
            self.client = await self.get_client()
        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=messages,
        )
        # Extract content from the async response
        return response.choices[0].message.content.strip()

    async def interpret(self, user_input: str) -> Dict:
        """
        Interprets the user input and returns a default intent payload.

        Args:
            user_input (str): The input message from the user.

        Returns:
            Dict: Default interpretation result with intent and message.
        """
        # Simple pass-through interpretation, kept async for interface consistency
        return {"intent": "default", "message": user_input}
