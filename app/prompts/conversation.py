def build_intention_prompt_instruction() -> dict:
    return {
        "role": "system",
        "content": """
            Actúas como un asistente conversacional inteligente.

            Se te proporciona un contexto de memoria en formato XML:
            <context>
                <fact_memory> ... </fact_memory>
                <summary_memory> ... </summary_memory>
            </context>

            A continuación recibirás un mensaje del usuario, marcado como <user_input>...</user_input>.

            Tu tarea es:
            1. Analizar si el mensaje del usuario puede ser respondido únicamente con el contexto provisto.
            2. Antes de considerar acceder al historial completo (memoria episódica), intenta responder usando solamente el contexto provisto y la memoria de trabajo (últimos mensajes de la conversación actual que todavía están disponibles).
            3. Solo si el usuario hace referencia explícita o implícita a recuerdos pasados —por ejemplo, preguntando algo que ya te haya dicho antes, mencionando “recuerdas”, “qué te dije”, o usando pronombres sin antecedente claro—, responde con:
            {"intention": "episodic_memory"}
            En cualquier otro caso, no recurras a la memoria episódica.
            4. Si el contexto actual y la memoria de trabajo son suficientes, responde con:
            {"intention": "none", "response": "<respuesta>"}

            No incluyas encabezados, explicaciones ni ningún otro contenido.
            """.strip()
    }


def build_intention_prompt_messages(fact_memory: str, summary_memory: str, working_memory_text: str, user_msg: str) -> list[dict]:
    return [
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
            "content": user_msg
        }
    ]