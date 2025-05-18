import os
from typing import Dict
from app.llm.base import LLMBase
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

    def generate_response(self, user_input: str, context: Dict = {}) -> str:
        """
        Generates a text response based on the user input.

        Args:
            user_input (str): Incoming message from user.
            context (Dict): Optional context.

        Returns:
            str: Generated response from the LLM.
        """
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "user", "content": user_input}
            ]
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
