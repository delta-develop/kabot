def build_intention_prompt_instruction() -> dict:
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

Tu tarea es identificar la intención detrás del mensaje del usuario. Evalúa cada uno de los siguientes casos de forma independiente y excluyente. Devuelve solo una de estas intenciones en formato JSON.

- Si el usuario se despide o expresa que la conversación ha terminado (ej. "gracias", "nos vemos", "hasta luego"), responde con:
  {"intention": "exit"}

- Si el usuario pregunta por Kavak, su funcionamiento, servicios, sedes o información general de la empresa, responde con:
  {"intention": "kavak_info"}

- Si el mensaje parece ser una consulta para buscar vehículos, responde con:
  {"intention": "search"}

- Si el mensaje se refiere a opciones de financiamiento, mensualidades o formas de pagar un vehículo a crédito:
    - Si puedes identificar el vehículo (por el mensaje o la memoria de trabajo), incluye los datos en XML:
      {"intention": "financing", "vehicle": "<vehiculo>...</vehiculo>"}
    - Si no puedes identificar el vehículo con certeza, responde solo con la intención:
      {"intention": "financing"}

- Si el mensaje requiere información previamente mencionada y no está presente en la memoria de trabajo, responde con:
  {"intention": "episodic_memory"}

- En cualquier otro caso, responde normalmente con:
  {"intention": "none", "response": "<respuesta>"}
  
- Si ya tienes información de contexto y recibes algún mensaje que pueda considerarse un saludo (ej "Hola", "hey", "hola de nuevo"), tu respuesta deberá incluir algo del contexto para enriqeucerla.

Asegúrate de analizar tanto el contexto como el contenido de <user_input>. No incluyas encabezados, explicaciones ni ningún otro contenido.
""".strip()
    }


def build_intention_prompt_messages(fact_memory: str, summary_memory: str, working_memory_text: str, user_msg: str) -> list[dict]:
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
                """.strip()
        },
        {
            "role": "user",
            "content": f"<user_input>{user_msg}</user_input>"
        }
    ]