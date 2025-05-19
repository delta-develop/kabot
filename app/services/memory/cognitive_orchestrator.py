from typing import List, Dict, Any
import json
from app.prompts.conversation import build_intention_prompt_messages, build_intention_prompt_instruction
from app.services.search.search_handler import perform_vehicle_search
from app.prompts.finance import FINANCE_PROMPT
from app.prompts.kavak import KAVAK_INFO_PROMPT
from app.prompts.summary import summarize_vehicle_results
from app.prompts.exit import EXIT_PROMPT



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
        history_text = self._format_history(working_context)

        # 3. Preparar prompt de intención (con rol system + contexto + user_input)
        facts, summary = await self._load_fact_and_summary_context(user_id)

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

        print(f"intention: {intention}")
        # 6. Si requiere historial, expandir contexto y volver a llamar al LLM
        if intention == "episodic_memory":
            llm_reply = await self._handle_episodic_memory_intention(user_id, user_msg)

        elif intention == "search":
            llm_reply = await self._handle_search_intention(user_id, user_msg)


        elif intention == "financing":
            llm_reply = await self._handle_financing_intention(user_id, user_msg, parsed)

        elif intention == "kavak_info":
            llm_reply = await self._handle_kavak_info_intention(user_id, user_msg)
            
        elif intention == "exit":
            llm_reply = await self._handle_exit_intention(user_id, user_msg)

        # 7. Guardar en memoria de trabajo solo si la intención es "none"
        else:
            await self._store_dialogue(user_id, user_msg, llm_reply)

        return llm_reply

    async def _load_fact_and_summary_context(self, user_id: str) -> tuple[str, str]:
        facts = await self.fact_memory.retrieve_from_memory(user_id) or ""
        summary = await self.summary_memory.retrieve_from_memory(user_id) or ""
        return facts, summary

    def _format_history(self, messages: List[Dict[str, str]]) -> str:
        """
        Formatea una lista de mensajes como bloques XML para el prompt.
        """
        history_text = ""
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            history_text += f"<{role}>{content}</{role}>\n"
        return history_text.strip()

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

    async def _store_dialogue(self, user_id: str, user_msg: str, assistant_msg: str):
        await self.working_memory.store_in_memory(user_id, [
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": assistant_msg}
        ])
        
    async def _handle_episodic_memory_intention(self, user_id: str, user_msg: str) -> str:
        history = await self.expand_context_from_long_term(user_id)
        history_text = self._format_history(history)
        facts, summary = await self._load_fact_and_summary_context(user_id)
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
        return await self.llm.generate_response(extended_messages)

    async def _handle_search_intention(self, user_id: str, user_msg: str) -> str:
        results = await perform_vehicle_search(user_msg, k=5)
        summary_prompt = await summarize_vehicle_results(results)
        llm_reply = await self.llm.generate_response([{"role": "user", "content": summary_prompt}])
        await self.working_memory.store_in_memory(user_id, [
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": f"<natural_language_summary>{llm_reply}</natural_language_summary>"},
            {"role": "assistant", "content": f"<vehicle_results>{json.dumps(results)}</vehicle_results>"}
        ])
        return llm_reply

    async def _handle_financing_intention(self, user_id: str, user_msg: str, parsed: dict) -> str:
        vehicle_data = parsed.get("vehicle_data", {})
        financing_prompt = FINANCE_PROMPT.format(user_input=user_msg, vehicle_data=vehicle_data)
        llm_reply = await self.llm.generate_response([{"role": "user", "content": financing_prompt}])
        await self._store_dialogue(user_id, user_msg, llm_reply)
        return llm_reply

    async def _handle_kavak_info_intention(self, user_id: str, user_msg: str) -> str:
        kavak_prompt = KAVAK_INFO_PROMPT.format(user_input=user_msg)
        llm_reply = await self.llm.generate_response([{"role": "user", "content": kavak_prompt}])
        await self._store_dialogue(user_id, user_msg, llm_reply)
        return llm_reply

    async def _handle_exit_intention(self, user_id: str, user_msg: str) -> str:
        history = await self.working_memory.retrieve_from_memory(user_id) or []
        history_text = self._format_history(history)
        facts, summary = await self._load_fact_and_summary_context(user_id)
        prompt = EXIT_PROMPT.format(user_input=user_msg, working_memory=history_text.strip(), facts=facts, summary=summary)
        llm_reply = await self.llm.generate_response([{"role": "user", "content": prompt}])
        await self._store_dialogue(user_id, user_msg, llm_reply)
        await self.persist_conversation_closure(user_id)
        return llm_reply