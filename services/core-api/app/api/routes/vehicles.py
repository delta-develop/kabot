import csv
import json
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.services.search.filters import FILTER_SCHEMAS, filters_to_sql
from app.services.storage.relational_storage import RelationalStorage
from app.utils.openai_utils import get_embedding

router = APIRouter()


def _validate_namespace(namespace: str) -> None:
    if namespace not in FILTER_SCHEMAS:
        allowed = ", ".join(sorted(FILTER_SCHEMAS))
        raise HTTPException(
            status_code=400,
            detail=f"Unknown namespace '{namespace}'. Allowed namespaces: {allowed}",
        )


def _normalize_row(row: dict[str, str], namespace: str) -> dict[str, Any]:
    return {
        "namespace": namespace,
        "external_id": row["sku"],
        "title": row["name"],
        "body": row["description"],
        "attributes": {
            "store": row["store"],
            "brand": row["brand"],
            "unit": row["unit"],
            "pack_size": float(row["pack_size"]),
            "price": float(row["price"]),
        },
    }


async def _write_batch(
    storage: RelationalStorage,
    records: list[dict[str, Any]],
) -> None:
    for record in records:
        record["embedding"] = await get_embedding(
            record["title"] + "\n\n" + record["body"]
        )
    await storage.upsert_items(records)


@router.post("/upload")
async def upload_csv(
    file: UploadFile = File(...),
    namespace: str = Query(...),
) -> dict[str, Any]:
    _validate_namespace(namespace)
    storage = RelationalStorage()
    records: list[dict[str, Any]] = []

    try:
        reader = csv.DictReader(line.decode("utf-8") for line in file.file)
        for row in reader:
            records.append(_normalize_row(row, namespace))
    except (csv.Error, KeyError, TypeError, ValueError, UnicodeDecodeError) as error:
        raise HTTPException(
            status_code=400,
            detail=f"Error processing CSV file: {error}",
        ) from error

    for offset in range(0, len(records), 10):
        await _write_batch(storage, records[offset : offset + 10])

    return {"message": "Upload successful", "records_processed": len(records)}


@router.get("/search")
async def search_catalog(
    namespace: str = Query(...),
    query: str = Query(...),
    filters: str = Query("{}"),
    k: int = Query(5, ge=1, le=100),
) -> list[dict[str, Any]]:
    _validate_namespace(namespace)
    try:
        parsed_filters = json.loads(filters)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="Invalid filters JSON") from error
    if not isinstance(parsed_filters, dict):
        raise HTTPException(status_code=400, detail="Filters must be a JSON object")
    try:
        filters_to_sql(namespace, parsed_filters)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    vector = await get_embedding(query)
    return await RelationalStorage().knn_search(
        namespace,
        vector,
        filters=parsed_filters,
        k=k,
    )
