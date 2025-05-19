from abc import ABC, abstractmethod
from typing import Dict


class LLMBase(ABC):
    """Abstract base class for Large Language Model (LLM) interactions."""

    @abstractmethod
    async def interpret(self, user_input: str) -> Dict[str, str]:
        """
        Analyze the user's input to determine intent and extract relevant keywords.

        Args:
            user_input (str): The input message from the user.

        Returns:
            Dict[str, str]: A dictionary containing the identified intent and any relevant keywords.
        """
        pass

    @abstractmethod
    async def generate_response(self, messages: list) -> str:
        """
        Generate a response based on a list of structured chat messages.

        Args:
            messages (list): A list of messages, where each message is a dictionary 
                             containing 'role' and 'content' keys.

        Returns:
            str: The generated response.
        """
        pass
