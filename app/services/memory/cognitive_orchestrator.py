from typing import List, Dict, Any
import json
from app.prompts.conversation import build_intention_prompt_messages, build_intention_prompt_instruction


class CognitiveOrchestrator:
    def __init__(self):
        self.working_memory = None
        self.fact_memory = None
        self.episodic_memory = None
        self.summary_memory = None
        self.llm = None


    async def load_initial_context(self, user_id: str) -> List[Dict[str, str]]:
        """
        Loads summary and relevant facts for the beginning of the conversation.
        """
        context = []

        facts = await self.fact_memory.retrieve_from_memory(user_id)
        if facts:
            context.append({"role": "system", "content": f"<context>Relevant facts: {str(facts)}</context>"})

        summary = await self.summary_memory.retrieve_from_memory(user_id)
        if summary:
            context.append({"role": "system", "content": f"<context>{summary}</context>"})

        if context:
            context.insert(0, {
                "role": "system",
                "content": "The following context has been retrieved from memory to help you understand the user. Do not repeat it."
            })

        return context

    async def handle_conversation_start(self, user_id: str) -> List[Dict[str, str]]:
        """
        UC01: When a new conversation starts, load the user's summarized memory and factual data
        to initialize the LLM context.
        Returns a structured list of messages for context priming.
        """
        context = await self.load_initial_context(user_id)
        await self.working_memory.store_in_memory(user_id, context)
        return context

    async def handle_incoming_message(self, user_id: str, user_msg: str) -> str:
        # 1. Recuperar contexto actual
        context = await self.working_memory.retrieve_from_memory(user_id)

        # 2. Si no hay contexto, cargar de Mongo y guardar en caché
        if not context:
            context = await self.load_initial_context(user_id)
            await self.working_memory.store_in_memory(user_id, context)

        # Incluir memoria de trabajo reciente como parte del contexto
        working_context = await self.working_memory.retrieve_from_memory(user_id) or []
        history_text = ""
        for msg in working_context:
            role = msg["role"]
            content = msg["content"]
            history_text += f"<{role}>{content}</{role}>\n"

        # 3. Preparar prompt de intención (con rol system + contexto + user_input)
        facts = await self.fact_memory.retrieve_from_memory(user_id) or ""
        summary = await self.summary_memory.retrieve_from_memory(user_id) or ""

        prompt_messages = build_intention_prompt_messages(facts, summary, history_text.strip(), user_msg)

        # 4. Enviar al LLM
        llm_raw = await self.llm.generate_response(prompt_messages)

        # 5. Parsear respuesta
        try:
            parsed = json.loads(llm_raw)
            intention = parsed.get("intention", "none")
            llm_reply = parsed.get("response", "")
        except Exception:
            intention = "none"
            llm_reply = llm_raw

        # 6. Si requiere historial, expandir contexto y volver a llamar al LLM
        if intention == "episodic_memory":
            history = await self.expand_context_from_long_term(user_id)

            history_text = ""
            for msg in history:
                role = msg["role"]
                content = msg["content"]
                history_text += f"<{role}>{content}</{role}>\n"

            context_with_history = [
                {
                    "role": "system",
                    "content": f"""
                        <context>
                            <fact_memory>{facts}</fact_memory>
                            <summary_memory>{summary}</summary_memory>
                            <history>
                            {history_text.strip()}
                            </history>
                        </context>
                        """.strip()
                }
            ]

            extended_messages = [
                build_intention_prompt_instruction(),
                *context_with_history,
                {"role": "user", "content": f"<user_input>{user_msg}</user_input>"}
            ]

            llm_reply = await self.llm.generate_response(extended_messages)

        # 7. Guardar en memoria de trabajo solo si la intención es "none"
        if intention == "none":
            await self.working_memory.store_in_memory(user_id, [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": llm_reply}
            ])

        return llm_reply

    async def expand_context_from_long_term(self, user_id: str) -> List[Dict[str, str]]:
        """
        UC03: If the assistant lacks sufficient context to respond accurately,
        retrieve the full episodic history from long-term memory and use it to enhance the prompt.
        """
        return await self.episodic_memory.retrieve_from_memory(user_id) or []

    async def persist_conversation_closure(self, user_id: str) -> None:
        """
        UC04a–c: Al final de la conversación, persistir el contenido de working_memory
        en memoria episódica, resumirlo, extraer hechos y limpiar working_memory.
        """
        data = await self.working_memory.retrieve_from_memory(user_id)
        print(f"[Closure] Retrieved working memory for {user_id}: {data}")
        if data:
            filtered = [msg for msg in data if msg.get("content")]
            await self.episodic_memory.store_in_memory(user_id, filtered)
            print("[Closure] Stored in episodic memory")
            await self.summary_memory.store_in_memory(user_id, filtered)
            print("[Closure] Stored in summary memory")
            await self.fact_memory.store_in_memory(user_id, filtered)
            print("[Closure] Stored in fact memory")
            await self.working_memory.delete_from_memory(user_id)
            print("[Closure] Working memory cleared")
            
    async def generate_and_merge_summary(self, user_id: str) -> None:
        """
        UC04b: Summarize the latest working memory content,
        merge it with the previous summary, and update the memory accordingly.
        """
        data = await self.working_memory.retrieve_from_memory(user_id)
        if data:
            await self.summary_memory.store_in_memory(user_id, {"data": data})

    async def extract_and_update_facts(self, user_id: str) -> None:
        """
        UC04c: Extract new structured facts from the latest interactions
        and update the factual memory store.
        """
        data = await self.working_memory.retrieve_from_memory(user_id)
        if data:
            await self.fact_memory.store_in_memory(user_id, {"data": data})
    
    @classmethod
    async def from_defaults(cls) -> "CognitiveOrchestrator":
        from app.services.memory.working_memory import WorkingMemory
        from app.services.memory.fact_memory import FactMemory
        from app.services.memory.episodic_memory import EpisodicMemory
        from app.services.memory.summary_memory import SummaryMemory
        from app.services.llm.openai_client import OpenAIClient        

        orchestrator = cls.__new__(cls)
        orchestrator.llm = OpenAIClient()
        orchestrator.working_memory = WorkingMemory()
        orchestrator.fact_memory = FactMemory(orchestrator.llm)
        orchestrator.episodic_memory = EpisodicMemory()
        orchestrator.summary_memory = SummaryMemory(orchestrator.llm)
        
        return orchestrator