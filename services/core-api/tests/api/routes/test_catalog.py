import os
from io import BytesIO
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func
from sqlmodel import SQLModel, select

from app.main import app
from app.services.search.filters import FILTER_SCHEMAS
from app.services.storage import relational_storage

client = TestClient(app)
error_client = TestClient(app, raise_server_exceptions=False)

CSV_HEADER = "sku,store,name,brand,unit,pack_size,price,stock,description\n"


def csv_row(index: int, external_id: str | None = None) -> str:
    return (
        f"{external_id or f'sku-{index}'},abarrotes,Salt {index},"
        f"Brand,caja,12,40.5,9,"
        f"Fine salt {index}\n"
    )


async def catalog_ids(namespace, external_ids):
    table = SQLModel.metadata.tables["catalog_item"]
    engine = relational_storage.engine
    assert engine is not None
    async with engine.connect() as connection:
        rows = (
            await connection.execute(
                select(table.c.external_id, table.c.id).where(
                    table.c.namespace == namespace,
                    table.c.external_id.in_(external_ids),
                )
            )
        ).all()
    return {row.external_id: str(row.id) for row in rows}


async def delete_catalog_items(namespace, external_ids):
    table = SQLModel.metadata.tables["catalog_item"]
    engine = relational_storage.engine
    assert engine is not None
    predicate = (table.c.namespace == namespace) & table.c.external_id.in_(external_ids)
    async with engine.begin() as connection:
        await connection.execute(delete(table).where(predicate))
    async with engine.connect() as connection:
        return (
            await connection.execute(
                select(func.count()).select_from(table).where(predicate)
            )
        ).scalar_one()


def test_upload_normalizes_embeds_and_upserts_in_batches_of_ten(mocker):
    storage = mocker.patch("app.api.routes.vehicles.RelationalStorage").return_value
    storage.upsert_items = AsyncMock()
    embedding = mocker.patch(
        "app.api.routes.vehicles.get_embedding",
        new_callable=AsyncMock,
        return_value=[0.0] * 1536,
    )
    payload = (CSV_HEADER + "".join(csv_row(index) for index in range(11))).encode()

    response = client.post(
        "/upload",
        params={"namespace": "restaurant-supplies"},
        files={"file": ("catalog.csv", BytesIO(payload), "text/csv")},
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Upload successful", "records_processed": 11}
    assert [len(call.args[0]) for call in storage.upsert_items.await_args_list] == [
        10,
        1,
    ]
    first_item = storage.upsert_items.await_args_list[0].args[0][0]
    assert first_item == {
        "namespace": "restaurant-supplies",
        "external_id": "sku-0",
        "title": "Salt 0",
        "body": "Fine salt 0",
        "attributes": {
            "store": "abarrotes",
            "brand": "Brand",
            "unit": "caja",
            "pack_size": 12.0,
            "price": 40.5,
        },
        "embedding": [0.0] * 1536,
    }
    assert "stock" not in first_item["attributes"]
    assert embedding.await_args_list[0].args == ("Salt 0\n\nFine salt 0",)


def test_upload_provider_failure_writes_none_of_the_current_batch(mocker):
    storage = mocker.patch("app.api.routes.vehicles.RelationalStorage").return_value
    storage.upsert_items = AsyncMock()
    mocker.patch(
        "app.api.routes.vehicles.get_embedding",
        new_callable=AsyncMock,
        side_effect=[[0.0] * 1536, RuntimeError("provider unavailable")],
    )
    payload = (CSV_HEADER + csv_row(1) + csv_row(2)).encode()

    response = error_client.post(
        "/upload",
        params={"namespace": "restaurant-supplies"},
        files={"file": ("catalog.csv", BytesIO(payload), "text/csv")},
    )

    assert response.status_code == 500
    storage.upsert_items.assert_not_awaited()


def test_upload_rejects_unknown_namespace():
    response = client.post(
        "/upload",
        params={"namespace": "unknown"},
        files={"file": ("catalog.csv", BytesIO(CSV_HEADER.encode()), "text/csv")},
    )

    assert response.status_code == 400
    assert "restaurant-supplies" in response.json()["detail"]


@pytest.mark.skipif(
    not os.getenv("POSTGRES_INTEGRATION_URL"),
    reason="POSTGRES_INTEGRATION_URL is not configured",
)
def test_uploading_same_csv_twice_preserves_row_count_and_ids(mocker, monkeypatch):
    token = uuid4().hex
    namespace = f"integration-upload-{token}"
    external_ids = [f"integration-upload-{token}-{index}" for index in range(2)]
    payload = (
        CSV_HEADER
        + "".join(
            csv_row(index, external_id)
            for index, external_id in enumerate(external_ids)
        )
    ).encode()
    monkeypatch.setattr(
        relational_storage,
        "DATABASE_URL",
        os.environ["POSTGRES_INTEGRATION_URL"],
    )
    monkeypatch.setitem(
        FILTER_SCHEMAS,
        namespace,
        FILTER_SCHEMAS["restaurant-supplies"],
    )
    mocker.patch(
        "app.api.routes.vehicles.get_embedding",
        new_callable=AsyncMock,
        return_value=[1.0] + [0.0] * 1535,
    )

    with TestClient(app) as integration_client:
        assert integration_client.portal is not None
        try:
            first_response = integration_client.post(
                "/upload",
                params={"namespace": namespace},
                files={"file": ("catalog.csv", BytesIO(payload), "text/csv")},
            )
            first_ids = integration_client.portal.call(
                catalog_ids,
                namespace,
                external_ids,
            )
            second_response = integration_client.post(
                "/upload",
                params={"namespace": namespace},
                files={"file": ("catalog.csv", BytesIO(payload), "text/csv")},
            )
            second_ids = integration_client.portal.call(
                catalog_ids,
                namespace,
                external_ids,
            )
        finally:
            residue_count = integration_client.portal.call(
                delete_catalog_items,
                namespace,
                external_ids,
            )
            engine = relational_storage.engine
            assert engine is not None
            integration_client.portal.call(engine.dispose)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert len(first_ids) == 2
    assert second_ids == first_ids
    assert residue_count == 0


def test_search_embeds_query_and_returns_knn_results(mocker):
    storage = mocker.patch("app.api.routes.vehicles.RelationalStorage").return_value
    storage.knn_search = AsyncMock(
        return_value=[
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "namespace": "restaurant-supplies",
                "external_id": "sku-1",
                "title": "Salt",
                "body": "Fine salt",
                "attributes": {"price": 40.5},
                "distance": 0.1,
            }
        ]
    )
    embedding = mocker.patch(
        "app.api.routes.vehicles.get_embedding",
        new_callable=AsyncMock,
        return_value=[0.0] * 1536,
    )

    response = client.get(
        "/search",
        params={
            "namespace": "restaurant-supplies",
            "query": "salt",
            "filters": '{"brand":"Chef\'s Choice"}',
            "k": 3,
        },
    )

    assert response.status_code == 200
    assert "embedding" not in response.json()[0]
    embedding.assert_awaited_once_with("salt")
    storage.knn_search.assert_awaited_once_with(
        "restaurant-supplies",
        [0.0] * 1536,
        filters={"brand": "Chef's Choice"},
        k=3,
    )


def test_search_rejects_invalid_json():
    response = client.get(
        "/search",
        params={
            "namespace": "restaurant-supplies",
            "query": "salt",
            "filters": "not-json",
        },
    )

    assert response.status_code == 400


def test_search_rejects_unknown_namespace():
    response = client.get(
        "/search",
        params={"namespace": "unknown", "query": "salt"},
    )

    assert response.status_code == 400
    assert "restaurant-supplies" in response.json()["detail"]


def test_search_rejects_invalid_filter():
    response = client.get(
        "/search",
        params={
            "namespace": "restaurant-supplies",
            "query": "salt",
            "filters": '{"unknown":"value"}',
        },
    )

    assert response.status_code == 400
    assert "unknown" in response.json()["detail"]


def test_search_rejects_k_outside_range():
    response = client.get(
        "/search",
        params={"namespace": "restaurant-supplies", "query": "salt", "k": 101},
    )

    assert response.status_code == 422
