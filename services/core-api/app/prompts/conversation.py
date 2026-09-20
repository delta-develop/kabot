def build_intention_prompt_instruction() -> dict:
    """
    Builds the system instruction for the conversational assistant.

    Returns:
        dict: A dictionary representing the system prompt with instructions.
    """
    return {
        "role": "system",
        "content": """
          Actúas como un asistente conversacional inteligente.

          Se te proporciona un contexto de memoria en formato XML:
          <context>
              <fact_memory> ... </fact_memory>
              <summary_memory> ... </summary_memory>
              <working_memory> ... </working_memory>
          </context>

          Recibirás el mensaje del usuario como: <user_input> ... </user_input>

          Tu tarea es responder al usuario de forma clara, natural y concisa utilizando el contexto provisto para mantener la continuidad de la conversación.

          - Si el mensaje requiere información presente en la memoria, utilízala para enriquecer tu respuesta de manera coherente.
          - Si el usuario saluda, responde amablemente incorporando elementos relevantes del contexto si están disponibles.
          - Devuelve directamente tu respuesta conversacional sin encabezados ni explicaciones adicionales.
          """.strip(),
    }


def build_intention_prompt_messages(
    fact_memory: str, summary_memory: str, working_memory_text: str, user_msg: str
) -> list[dict]:
    """
    Builds the list of prompt messages for intention identification, including context and user input.

    Args:
        fact_memory (str): The factual memory context.
        summary_memory (str): The summary memory context.
        working_memory_text (str): The working memory context.
        user_msg (str): The user's message.

    Returns:
        list[dict]: A list of dictionaries representing the conversation messages for the prompt.
    """
    return [
        build_intention_prompt_instruction(),
        {
            "role": "system",
            "content": f"""
                <context>
                    <fact_memory>{fact_memory}</fact_memory>
                    <summary_memory>{summary_memory}</summary_memory>
                    <working_memory>{working_memory_text}</working_memory>
                </context>
                """.strip(),
        },
        {"role": "user", "content": f"<user_input>{user_msg}</user_input>"},
    ]
