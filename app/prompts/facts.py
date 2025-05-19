async def build_fact_merge_prompt(recent_messages: list, previous_facts: dict) -> dict:
    """
    Construye un prompt para actualizar o fusionar hechos relevantes sobre el usuario basándose en su historial de conversación reciente.

    Args:
        recent_messages (list): Lista de mensajes recientes en formato {'role': ..., 'content': ...}.
        previous_facts (dict): Diccionario con los hechos previamente almacenados del usuario.

    Returns:
        dict: Un diccionario con el rol 'system' y el contenido del prompt construido.
    """
    formatted_history = "\n".join(
        f"{m['role']}: {m['content']}" for m in recent_messages
    )
    formatted_facts = ", ".join(f"{k}: {v}" for k, v in previous_facts.items())

    return {
        "role": "system",
        "content": f"""
            Actúa como un motor de extracción y mantenimiento de hechos relevantes para una inteligencia artificial conversacional.

            Tienes dos tareas:
            1. A partir del historial de mensajes, extrae hechos importantes sobre el usuario, como su nombre, preferencias, gustos, datos de contacto o cualquier información persistente que pueda ayudar a personalizar futuras respuestas.
            2. Fusiona estos nuevos hechos con los existentes. Si hay conflicto directo entre un hecho previo y uno nuevo (por ejemplo, cambia de marca favorita), actualiza el valor. Si el nuevo hecho complementa la información anterior, añádelo sin eliminar lo ya guardado.
            
            Si los hechos actuales conocidos son 'Ninguno', genera una nueva estructura base a partir de la conversación reciente.

            Hechos actuales conocidos:
            {formatted_facts or 'Ninguno'}

            Historial reciente de conversación:
            <conversation>
            {formatted_history}
            </conversation>

            Devuelve únicamente un objeto JSON con los hechos actualizados del usuario. No lo encierres en bloques de código ni lo formatees como Markdown. No incluyas explicaciones ni formato adicional.        """.strip(),
    }
