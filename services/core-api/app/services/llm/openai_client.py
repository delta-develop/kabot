from typing import Any, Dict, List

from app.services.llm.base import LLMBase
from app.services.storage.connections import get_openai_client
from app.utils.openai_utils import get_chat_model, get_reasoning_effort


class OpenAIClient(LLMBase):
    """Asynchronous OpenAI client that implements the LLMBase interface.

    This client handles generating responses from a chat-based language model
    and interpreting user input.
    """

    def __init__(self):
        """Initializes the OpenAIClient with model parameters from environment variables."""
        self.model = get_chat_model()
        self.reasoning_effort = get_reasoning_effort()
        self.client = None

    async def get_client(self):
        """Lazily initializes and returns the OpenAI client.

        Returns:
            An instance of the OpenAI client.
        """
        if self.client is None:
            self.client = await get_openai_client()
        return self.client

    async def generate_response(
        self, messages: List[Dict], as_json: bool = False
    ) -> str:
        """Generates a response from the language model based on the given message history.

        Args:
            messages (List[Dict]): A list of message dictionaries representing the conversation history.
            as_json (bool): Constrain the reply to a single JSON object. Asking for
                JSON in the prompt is a request; this is a guarantee.

        Returns:
            str: The generated response from the language model.
        """
        if not self.client:
            self.client = await self.get_client()
        # No `temperature`: the gpt-5 line answers 400 for any value but the
        # default. Output is steered with reasoning effort instead.
        options: dict[str, Any] = {}
        if self.reasoning_effort:
            options["reasoning_effort"] = self.reasoning_effort
        if as_json:
            options["response_format"] = {"type": "json_object"}
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **options,
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
