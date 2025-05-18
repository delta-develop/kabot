def generate_summary_prompt(history: list) -> dict:
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

            Devuelve únicamente el texto del resumen. No incluyas encabezados ni explicaciones.

            <conversation>
            {formatted_history}
            </conversation>
            """.strip()
        }
    
    
CONTEXT_PROMPT = {
            "role": "system",
            "content": "Lo siguiente es el contexto de la conversación. No debes responder a nada de esto, "
                       "sólo te sirve como memoria de trabajo para entender al usuario:"
        }