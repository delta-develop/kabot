from typing import List, Dict


def to_openai_format(messages: List[Dict]) -> List[Dict]:
    """
    Convierte una lista de mensajes en cualquier estructura válida
    al formato esperado por OpenAI: [{role, content}]
    """
    formatted = []
    for m in messages:
        role = m.get("role")
        content = m.get("content")

        if not role or not content:
            continue  # opcional: podrías hacer logging si falta algo

        formatted.append({"role": str(role), "content": str(content)})

    return formatted
