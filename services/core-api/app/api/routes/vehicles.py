import csv
from typing import List

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.models.vehicle import Vehicle
from app.services.search.search_handler import perform_vehicle_search
from app.services.storage.relational_storage import RelationalStorage
from app.utils.helpers import parse_bool, parse_float

router = APIRouter()


@router.get("/search")
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


@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)) -> dict:
    """
    Uploads a CSV file and ingests the data into PostgreSQL in chunks.

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
                total_processed += len(records)
                records = []

        if records:
            await relational_storage.bulk_load({"records": records})
            total_processed += len(records)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing CSV file: {e}")

    return {"message": "Upload successful", "records_processed": total_processed}
