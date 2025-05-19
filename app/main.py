# Standard library imports
import asyncio
import csv
import os

# Third-party imports
import dotenv
from fastapi import (
    APIRouter,
    FastAPI,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
)

# Local application/library specific imports
from app.models.vehicle import Vehicle
from app.services.memory.cognitive_orchestrator import CognitiveOrchestrator
from app.services.storage.cache_storage import CacheStorage
from app.services.storage.relational_storage import RelationalStorage
from app.services.storage.search_engine_storage import SearchEngineStorage
from app.utils.helpers import parse_bool, parse_float
from app.utils.messaging import send_whatsapp_message
from app.utils.sanitization import sanitize_message


dotenv.load_dotenv()
app = FastAPI()
router = APIRouter()


@router.post("/upload")
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

            if len(records) == 100:
                await asyncio.gather(
                    relational_storage.bulk_load({"records": records}),
                    search_engine_storage.bulk_load({"records": records}),
                )
                total_processed += len(records)
                records = []

        if records:
            await asyncio.gather(
                relational_storage.bulk_load({"records": records}),
                search_engine_storage.bulk_load({"records": records}),
            )
            total_processed += len(records)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing CSV file: {e}")

    return {"message": "Upload successful", "records_processed": total_processed}


app.include_router(router)


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    user_msg = sanitize_message(form.get("Body"))
    raw_from = form.get("From") 
    from_number = raw_from.split(":")[-1].replace("+", "")

    orchestrator = await CognitiveOrchestrator.from_defaults()
    response_text = await orchestrator.handle_incoming_message(from_number, user_msg)

    return Response(status_code=200, content=response_text)


@app.post("/debug/migrate-memory")
async def migrate_memory_endpoint(user_id: str):
    try:
        print(user_id)
        orchestrator = await CognitiveOrchestrator.from_defaults()
        await orchestrator.persist_conversation_closure(user_id)
        return {"message": f"Memoria migrada correctamente para el usuario {user_id}"}
    except Exception as e:
        return {"error": str(e)}


# Author information endpoint
@app.get("/author")
async def get_author():
    return {
        "name": "Leonardo HG",
        "location": "Ciudad de México",
        "role": "Backend Developer",
        "project": "Tech Challenge - Kabot",
    }
