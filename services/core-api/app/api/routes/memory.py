from fastapi import APIRouter

from app.services.memory.cognitive_orchestrator import CognitiveOrchestrator

router = APIRouter()


@router.post("/debug/migrate-memory")
async def migrate_memory_endpoint(user_id: str):
    """
    Triggers the persistence of memory data to long-term storage for the given user ID.

    Args:
        user_id (str): The user's phone number identifier.

    Returns:
        dict: Result message or error.
    """
    try:
        orchestrator = await CognitiveOrchestrator.from_defaults()
        await orchestrator.persist_conversation_closure(user_id)
        return {"message": f"Memoria migrada correctamente para el usuario {user_id}"}
    except Exception as e:
        return {"error": str(e)}
