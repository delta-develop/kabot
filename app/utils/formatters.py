from typing import List, Dict


def to_openai_format(messages: List[Dict]) -> List[Dict]:
    """Convierte una lista de mensajes a formato compatible con OpenAI.

    Args:
        messages (List[Dict]): Lista de mensajes con claves 'role' y 'content'.

    Returns:
        List[Dict]: Lista de mensajes formateados según lo esperado por OpenAI.
    """
    formatted = []
    for m in messages:
        role = m.get("role")
        content = m.get("content")

        if not role or not content:
            continue

        formatted.append({"role": str(role), "content": str(content)})

    return formatted
