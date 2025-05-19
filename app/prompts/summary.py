import json

async def build_summary_merge_prompt(recent_messages: list, previous_summary: str) -> dict:
    if not recent_messages and not previous_summary:
        return {
            "role": "system",
            "content": "No hay historial ni resumen previo disponible. No es posible generar un resumen en este momento."
        }

    formatted_history = "\n".join(f"{m['role']}: {m['content']}" for m in recent_messages)

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
                """.strip()
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
            """.strip()
                }
    
    
async def generate_summary_prompt(history: list) -> dict:
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
            - No incluyas intereses, marcas o modelos si el usuario no los mencionó directamente y de manera positiva.
            - También incluye rechazos explícitos del usuario hacia ciertas marcas, modelos, tipos de auto o características, si existen.
            - Si el usuario expresó desinterés o rechazo por alguna marca o modelo (como Toyota o híbridos), nunca lo menciones como recomendación.
            - Si no estás completamente seguro del interés actual del usuario en un modelo específico, omite mencionarlo. Opta por una despedida general y cálida.

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


async def summarize_vehicle_results(results: list) -> str:
        """
        Uses the LLM to summarize a list of vehicle search results into a user-friendly message.
        """
        formatted_results = json.dumps(results, indent=2, ensure_ascii=False)
        prompt = VEHICLE_SUMMARIZATION_PROMPT.format(results=formatted_results)
        return prompt
    
VEHICLE_SUMMARIZATION_PROMPT = """
    A continuación tienes una lista de vehículos que coinciden con los intereses del usuario.

    Tu tarea es generar un mensaje en lenguaje natural que resuma los resultados de forma clara y amigable. Incluye lo siguiente:
    - El número de coincidencias encontradas
    - Una breve descripción de los modelos más destacados (máximo 3)
    - Destacar si tienen características importantes como CarPlay o Bluetooth
    - Mencionar el rango de precios y años si hay variedad
    - Usar un tono cordial y útil, como si fueras un asesor

    Resultados:
    {results}

    Responde únicamente con el mensaje dirigido al usuario. No expliques tu razonamiento.
    """.strip()
