from typing import List


def format_conversation(messages: List[dict]) -> List[dict[str, str]]:
    """Clean and prepare a message list for LLM input.

    Args:
        messages (List[dict]): A list of dictionaries representing messages.

    Returns:
        List[dict[str, str]]: A filtered and stripped list of messages suitable for LLM input.
    """
    return [
        {"role": m["role"], "content": m["content"].strip()}
        for m in messages
        if m.get("role") in {"user", "assistant", "system"} and m.get("content")
    ]


def message_from_user_input(text: str) -> dict[str, str]:
    """Convert raw user text into a format compatible with the LLM.

    Args:
        text (str): The user's message.

    Returns:
        dict[str, str]: A dictionary representing a user message.
    """
    return {"role": "user", "content": text.strip()}


def message_from_llm_output(text: str) -> dict[str, str]:
    """Convert raw LLM output into a message format for memory.

    Args:
        text (str): The LLM's response text.

    Returns:
        dict[str, str]: A dictionary representing an assistant message.
    """
    return {"role": "assistant", "content": text.strip()}
