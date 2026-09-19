import os
from typing import Dict, List

from app.services.llm.base import LLMBase
from app.services.storage.connections import get_openai_client


class OpenAIClient(LLMBase):
    """Asynchronous OpenAI client that implements the LLMBase interface.

    This client handles generating responses from a chat-based language model
    and interpreting user input.
    """

    def __init__(self):
        """Initializes the OpenAIClient with model parameters from environment variables."""
        self.model = os.getenv("OPENAI_MODEL")
        self.temperature = float(os.getenv("OPENAI_TEMPERATURE", 0.7))
        self.client = None

    async def get_client(self):
        """Lazily initializes and returns the OpenAI client.

        Returns:
            An instance of the OpenAI client.
        """
        if self.client is None:
            self.client = await get_openai_client()
        return self.client

    async def generate_response(self, messages: List[Dict]) -> str:
        """Generates a response from the language model based on the given message history.

        Args:
            messages (List[Dict]): A list of message dictionaries representing the conversation history.

        Returns:
            str: The generated response from the language model.
        """
        if not self.client:
            self.client = await self.get_client()
        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=messages,
        )
        return response.choices[0].message.content.strip()

    async def interpret(self, user_input: str) -> Dict:
        """Interprets user input and returns a basic intent response.

        Args:
            user_input (str): The raw input text from the user.

        Returns:
            Dict: A dictionary containing the inferred intent and the original message.
        """
        return {"intent": "default", "message": user_input}
