from app.models.session import TurnDraft


async def build_summary_merge_prompt(
    recent_messages: list[TurnDraft], previous_summary: str
) -> dict:
    """
    Construye un prompt para que el LLM genere o fusione un resumen conversacional.

    Args:
        recent_messages (list): Lista de mensajes recientes de la conversación.
        previous_summary (str): Resumen anterior almacenado.

    Returns:
        dict: Objeto con rol y contenido para el LLM.
    """
    if not recent_messages and not previous_summary:
        return {
            "role": "system",
            "content": "No hay historial ni resumen previo disponible. No es posible generar un resumen en este momento.",
        }

    formatted_history = "\n".join(
        f"user: {turn.user_text}\nassistant: {turn.assistant_text}"
        for turn in recent_messages
    )

    if not previous_summary:
        return {
            "role": "system",
            "content": f"""
                Actúa como una memoria de resumen para una inteligencia artificial conversacional.

                Tu tarea es generar un TL;DR a partir de los mensajes recientes de una conversación entre un usuario y un asistente. El resumen debe capturar la intención, tono, preguntas importantes, respuestas clave y cualquier información personal relevante.

                Mensajes recientes:
                <conversation>
                {formatted_history}
                </conversation>

                Devuelve únicamente el resumen generado. No incluyas encabezados ni explicaciones.
                """.strip(),
        }

    return {
        "role": "system",
        "content": f"""
            Actúa como una memoria de resumen para una inteligencia artificial conversacional.

            Tu tarea consiste en dos pasos:
            1. Leer los mensajes recientes de una conversación entre un usuario y un asistente, y generar un nuevo TL;DR que capte su intención, tono, preguntas importantes, respuestas clave y cualquier información personal relevante.
            2. Fusionar ese nuevo resumen con el resumen anterior ya existente, generando uno solo que combine todo el contexto de forma coherente y compacta.

            Resumen anterior:
            {previous_summary}

            Mensajes recientes:
            <conversation>
            {formatted_history}
            </conversation>

            Devuelve únicamente el nuevo resumen combinado. No incluyas encabezados ni explicaciones.
            """.strip(),
    }


async def generate_summary_prompt(history: list) -> dict:
    """
    Genera un prompt para resumir una conversación completa.

    Args:
        history (list): Historial completo de mensajes.

    Returns:
        dict: Prompt estructurado para el LLM.
    """
    formatted_history = "\n".join(f"{m['role']}: {m['content']}" for m in history)

    return {
        "role": "system",
        "content": f"""
            Actúa como un sistema de memoria de trabajo para una inteligencia artificial conversacional.

            Tu tarea es resumir de forma compacta los siguientes mensajes de una conversación entre un usuario y un asistente.

            El resumen debe conservar el contexto necesario para continuar la conversación fluidamente, sin perder detalles importantes.

            Incluye en el resumen:
            - Intención del usuario si se puede deducir
            - Preguntas clave que haya hecho
            - Respuestas del asistente que aporten al flujo
            - Datos personales o preferencias compartidas por el usuario (si existen)
            - Cualquier emoción, actitud o tono relevante

            Escribe el resumen en tercera persona, de manera objetiva, sin agregar opiniones ni usar frases como 'el asistente dijo'.

            Muy importante:
            - NO asumas que una sugerencia hecha por el asistente fue aceptada por el usuario a menos que haya una afirmación explícita (por ejemplo, "me interesa", "quiero ese", "me gusta", etc.)
            - Ignora información que fue solamente propuesta por el asistente y no confirmada por el usuario.
            - No incluyas intereses o preferencias si el usuario no los mencionó directamente y de manera positiva.
            - También incluye rechazos explícitos del usuario hacia ciertos temas, preferencias o características, si existen.
            - Si el usuario expresó desinterés o rechazo por algún elemento, no lo menciones como recomendación.
            - Si no estás completamente seguro del interés actual del usuario en un tema específico, omite mencionarlo.

            Devuelve únicamente el texto del resumen. No incluyas encabezados ni explicaciones.

            <conversation>
            {formatted_history}
            </conversation>
            """.strip(),
    }


CONTEXT_PROMPT = {
    "role": "system",
    "content": "Lo siguiente es el contexto de la conversación. No debes responder a nada de esto, "
    "sólo te sirve como memoria de trabajo para entender al usuario:",
}
