import os
from typing import Dict
from app.services.llm.base import LLMBase
from openai import OpenAI
import dotenv

dotenv.load_dotenv()

class OpenAIClient(LLMBase):
    """
    OpenAI client for generating responses from user messages.
    """

    def __init__(self):
        self.model = os.getenv("OPENAI_MODEL")
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.temperature = float(os.getenv("OPENAI_TEMPERATURE"))

    def generate_response(self, messages: list) -> str:
        """
        Generates a text response from a list of messages in OpenAI format.

        Args:
            messages (list): A list of message dicts with roles and contents.

        Returns:
            str: Generated response from the LLM.
        """
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=messages
        )
        return response.choices[0].message.content.strip()

    def interpret(self, user_input: str) -> Dict:
        """
        Placeholder method for future intent detection logic.

        Args:
            user_input (str): Incoming message from user.

        Returns:
            Dict: Default interpretation payload.
        """
        return {"intent": "default", "message": user_input}
