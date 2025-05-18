from abc import ABC, abstractmethod
from typing import Any, Dict

class LLMBase(ABC):
    
    @abstractmethod
    def interpret(self, user_input: str) -> Dict[str, Any]:
        """Devuelve intención y posibles keywords."""
        pass

    @abstractmethod
    def generate_response(self, user_input: str, context: Dict[str, Any]) -> str:
        """Genera una respuesta natural para el usuario."""
        pass