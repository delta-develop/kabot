# Standard library imports
import csv

# Third-party imports
import dotenv
from fastapi import (
    APIRouter,
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from typing import List

# Local application/library specific imports
import openai
from app.utils.openai_utils import get_embedding
from app.utils.description import build_vehicle_description
from app.models.vehicle import Vehicle
from app.services.memory.cognitive_orchestrator import CognitiveOrchestrator
from app.services.storage.relational_storage import RelationalStorage
from app.services.storage.search_engine_storage import SearchEngineStorage
from app.utils.helpers import parse_bool, parse_float
from app.utils.messaging import send_whatsapp_message
from app.utils.sanitization import sanitize_message
from app.services.search.search_handler import perform_vehicle_search

dotenv.load_dotenv()
app = FastAPI()
router = APIRouter()
app.include_router(router)


@app.get("/search")
async def search_similar_vehicles(query: str = Query(...), k: int = 5) -> List[dict]:
    """
    Performs a semantic search over the vehicle index using the user's query.
    Extracts structured filters using a language model before searching.

    Args:
        query (str): User's search input.
        k (int): Number of similar results to return.

    Returns:
        List[dict]: Matching vehicles with metadata.
    """

    try:
        results = await perform_vehicle_search(query, k)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {e}")


@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)) -> dict:
    """
    Uploads a CSV file and ingests the data into PostgreSQL and OpenSearch in chunks.

    Args:
        file (UploadFile): CSV file uploaded by the user.

    Returns:
        dict: Result summary.
    """
    try:
        reader = csv.DictReader(line.decode("utf-8") for line in file.file)
        records = []
        total_processed = 0

        relational_storage = RelationalStorage()
        search_engine_storage = SearchEngineStorage()

        for row in reader:
            try:
                record = Vehicle(
                    stock_id=int(row["stock_id"]),
                    km=int(row["km"]),
                    price=parse_float(row["price"]),
                    make=row["make"],
                    model=row["model"],
                    year=int(row["year"]),
                    version=row["version"],
                    bluetooth=parse_bool(row["bluetooth"]),
                    largo=parse_float(row["largo"]),
                    ancho=parse_float(row["ancho"]),
                    altura=parse_float(row["altura"]),
                    car_play=parse_bool(row["car_play"]),
                )
                records.append(record.model_dump())
            except (ValueError, KeyError) as e:
                raise HTTPException(status_code=400, detail=f"Invalid data format: {e}")

            if len(records) == 10:
                await relational_storage.bulk_load({"records": records})
                for record in records:
                    vehicle = Vehicle(**record)
                    description = build_vehicle_description(vehicle)
                    vector = await get_embedding(description)
                    await search_engine_storage.index_with_embedding(
                        description, record, vector
                    )
                total_processed += len(records)
                records = []

        if records:
            await relational_storage.bulk_load({"records": records})
            for record in records:
                vehicle = Vehicle(**record)
                description = build_vehicle_description(vehicle)
                vector = await get_embedding(description)
                await search_engine_storage.index_with_embedding(
                    description, record, vector
                )
            total_processed += len(records)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing CSV file: {e}")

    return {"message": "Upload successful", "records_processed": total_processed}


@app.post("/webhook/whatsapp")
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


@app.post("/debug/migrate-memory")
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


# Author information endpoint
@app.get("/author")
async def get_author():
    """
    Returns author metadata for the project.

    Returns:
        dict: Author information.
    """
    return {
        "name": "Leonardo HG",
        "location": "Ciudad de México",
        "role": "Backend Developer",
        "project": "Tech Challenge - Kabot",
    }
