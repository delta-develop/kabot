from app.models.context import Context
from app.utils.token_utils import count_tokens


def build_conversation_instruction() -> dict:
    """
    Builds the system instruction for the conversational assistant.

    Returns:
        dict: A dictionary representing the system prompt with instructions.
    """
    return {
        "role": "system",
        "content": """
          Actúas como un asistente conversacional inteligente.

          El contexto trae, en este orden: hechos del usuario, un resumen,
          turnos recordados bajo su fecha, y la conversación en curso. Las
          líneas indentadas continúan el turno anterior.

          - Usa la memoria para dar continuidad; responde claro y conciso.
          - Los hechos son un resumen que puede estar desactualizado. Los turnos
            fechados son textuales y tienen precedencia.
          - Responde directamente, sin encabezados ni explicaciones.
          """.strip(),
    }


def escape_markup(text: str) -> str:
    """Stop untrusted text from forging a turn or a section header.

    Every line after the first is indented, so nothing inside the content sits
    at column 0, where the role prefixes and the `##` headers live. A message
    holding a line that reads `Assistant: ...` therefore stays inside the turn
    the subject actually wrote.

    It costs nothing on single-line text, which is the common case, and it also
    makes a multi-line answer visibly part of the turn it belongs to.
    """
    return text.replace("\n", "\n  ")


def render_memory(context: Context) -> str:
    """Concatenate the context blocks exactly as they were counted."""
    return "".join(block.content for block in context.blocks)


def render_user_message(user_msg: str) -> str:
    """The live message reaches the model verbatim.

    It travels in its own `user` message, so it sits next to nothing it could
    forge a turn against. It is escaped later, once it becomes working memory.
    """
    return user_msg


def scaffolding_tokens() -> int:
    """Count everything in the prompt that is neither memory nor the message."""
    return count_tokens(build_conversation_instruction()["content"])


def build_conversation_prompt(context: Context, user_msg: str) -> list[dict]:
    """
    Builds the prompt messages from an assembled context and the user input.

    Args:
        context (Context): The memory blocks that fit in the budget, in reading
            order.
        user_msg (str): The user's message.

    Returns:
        list[dict]: A list of dictionaries representing the conversation messages for the prompt.
    """
    return [
        build_conversation_instruction(),
        {"role": "system", "content": render_memory(context)},
        {"role": "user", "content": render_user_message(user_msg)},
    ]
