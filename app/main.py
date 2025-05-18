import csv
from io import StringIO
from fastapi import APIRouter, UploadFile, File, HTTPException, FastAPI, Request, Response
import asyncio
from app.models.vehicle import Vehicle
from app.storage.relational_storage import RelationalStorage
from app.storage.search_engine_storage import SearchEngineStorage

from app.utils.helpers import chunk_records, parse_bool, parse_float

from app.llm.openai_client import OpenAIClient

from app.utils.messaging import send_whatsapp_message


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
                    asyncio.to_thread(relational_storage.bulk_load, {"records": records}),
                    asyncio.to_thread(search_engine_storage.bulk_load, {"records": records}),
                )
                total_processed += len(records)
                records = []

        if records:
            await asyncio.gather(
                asyncio.to_thread(relational_storage.bulk_load, {"records": records}),
                asyncio.to_thread(search_engine_storage.bulk_load, {"records": records}),
            )
            total_processed += len(records)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing CSV file: {e}")

    return {"message": "Upload successful", "records_processed": total_processed}


app.include_router(router)


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    llm = OpenAIClient()
    form = await request.form()
    user_msg = form.get("Body")
    from_number = form.get("From")
    
    print(f"Mensaje de {from_number}: {user_msg}")
    
    response_text = llm.generate_response(user_msg)
    
    print(f"Respuesta generada: {response_text}")
    
    send_whatsapp_message(from_number, response_text)
    
    return Response(status_code=200)




# Author information endpoint
@app.get("/author")
async def get_author():
    return {
        "name": "Leonardo HG",
        "location": "Ciudad de México",
        "role": "Backend Developer",
        "project": "Tech Challenge - Kabot"
    }