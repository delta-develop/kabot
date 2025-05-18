import csv
from io import StringIO
from fastapi import APIRouter, UploadFile, File, HTTPException, FastAPI, Request, Response
import asyncio
from app.models.vehicle import Vehicle
from app.services.storage.relational_storage import RelationalStorage
from app.services.storage.search_engine_storage import SearchEngineStorage

from app.utils.helpers import parse_bool, parse_float

from app.services.llm.openai_client import OpenAIClient

from app.utils.messaging import send_whatsapp_message

from app.services.memory.memory import RedisWorkingMemory

from app.prompts.summary import generate_summary_prompt, CONTEXT_PROMPT

import dotenv

import os


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
    memory = RedisWorkingMemory()

    MAX_TURNS = os.getenv("MAX_TURNS",10)

    form = await request.form()
    user_msg = form.get("Body")
    from_number = form.get("From")

    await memory.append_turn(from_number, role="user", content=user_msg)

    history = await memory.get(from_number) or []
    
    # Si el historial supera el límite, resumirlo
    if len(history) >= MAX_TURNS:        
        summary_prompt = [{
          "role":"system",
          "content":generate_summary_prompt(history)  
        }]
            
        summary = llm.generate_response(summary_prompt)
        
        # Reemplaza el historial con el resumen y el mensaje actual del usuario
        await memory.set(from_number, [
            {"role": "system", "content": summary},
            {"role": "user", "content": user_msg}
        ])
        history = [
            {"role": "system", "content": summary},
            {"role": "user", "content": user_msg}
        ]
        

    # Solo agregar el mensaje actual del usuario si no está ya incluido en el historial
    if not any(m["content"] == user_msg and m["role"] == "user" for m in history):
        history.append({"role": "user", "content": user_msg})

    messages = [CONTEXT_PROMPT] + history
    
    response_text = llm.generate_response(messages)

    await memory.append_turn(from_number, role="system", content=response_text)

    # send_whatsapp_message(from_number, response_text)

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