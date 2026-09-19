from fastapi import APIRouter, Request, Response

from app.services.memory.cognitive_orchestrator import CognitiveOrchestrator
from app.utils.messaging import send_whatsapp_message
from app.utils.sanitization import sanitize_message

router = APIRouter()


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Receives incoming messages from WhatsApp, processes them through the orchestrator,
    and sends a response using the Twilio messaging service.

    Args:
        request (Request): Incoming HTTP request from Twilio containing message data.

    Returns:
        Response: HTTP response with status 200 and response text.
    """
    form = await request.form()
    user_msg = sanitize_message(form.get("Body"))
    raw_from = form.get("From")
    from_number = raw_from.split(":")[-1].replace("+", "")
    sandbox = form.get("Sandbox")

    orchestrator = await CognitiveOrchestrator.from_defaults()
    response_text = await orchestrator.handle_incoming_message(from_number, user_msg)

    print(f"response_text {response_text}")

    if not sandbox:
        send_whatsapp_message(raw_from, response_text)

    return Response(status_code=200, content=response_text)
