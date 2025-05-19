from abc import ABC, abstractmethod
from typing import Any, Dict


class LLMBase(ABC):
    @abstractmethod
    async def interpret(self, user_input: str) -> Dict[str, Any]:
        """Returns intent and possibly relevant keywords from user input."""
        pass

    @abstractmethod
    async def generate_response(self, messages: list) -> str:
        """Generates a response from a list of chat-formatted messages."""
        pass
