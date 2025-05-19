from typing import List, Dict

def format_conversation(messages: List[Dict]) -> List[Dict[str, str]]:
    """
    Cleans and prepares a message list for LLM input.
    """
    return [
        {"role": m["role"], "content": m["content"].strip()}
        for m in messages
        if m.get("role") in {"user", "assistant", "system"} and m.get("content")
    ]

def message_from_user_input(text: str) -> Dict[str, str]:
    """
    Converts raw user text into LLM-compatible format.
    """
    return {"role": "user", "content": text.strip()}

def message_from_llm_output(text: str) -> Dict[str, str]:
    """
    Converts raw LLM output into message format for memory.
    """
    return {"role": "assistant", "content": text.strip()}