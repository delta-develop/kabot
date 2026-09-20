import os
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from sqlalchemy import delete, func
from sqlmodel import SQLModel, select

from app.services.search.filters import FILTER_SCHEMAS
from app.services.storage import relational_storage
from app.services.storage.relational_storage import RelationalStorage

INTEGRATION_DATABASE_URL = os.getenv("POSTGRES_INTEGRATION_URL")
pytestmark = pytest.mark.skipif(
    not INTEGRATION_DATABASE_URL,
    reason="POSTGRES_INTEGRATION_URL is not configured",
)


def item(namespace, external_id, vector, **changes):
    value = {
        "namespace": namespace,
        "external_id": external_id,
        "title": "Original title",
        "body": "Original body",
        "attributes": {
            "store": "integration",
            "brand": "integration",
            "unit": "piece",
            "pack_size": 1,
            "price": 10,
        },
        "embedding": vector,
    }
    value.update(changes)
    return value


@asynccontextmanager
async def integration_storage(monkeypatch):
    monkeypatch.setattr(
        relational_storage,
        "DATABASE_URL",
        INTEGRATION_DATABASE_URL,
    )
    storage = RelationalStorage()
    await storage.setup()
    try:
        yield storage
    finally:
        assert storage.engine is not None
        await storage.engine.dispose()


async def delete_items(storage, namespace, external_ids):
    table = SQLModel.metadata.tables["catalog_item"]
    predicate = (table.c.namespace == namespace) & table.c.external_id.in_(external_ids)
    assert storage.engine is not None
    async with storage.engine.begin() as connection:
        await connection.execute(delete(table).where(predicate))
    async with storage.engine.connect() as connection:
        count = (
            await connection.execute(
                select(func.count()).select_from(table).where(predicate)
            )
        ).scalar_one()
    assert count == 0


@pytest.mark.asyncio
async def test_repeated_upsert_preserves_id_and_updates_four_columns(monkeypatch):
    token = uuid4().hex
    namespace = f"integration-upsert-{token}"
    external_id = f"integration-upsert-{token}"
    original_vector = [1.0] + [0.0] * 1535
    updated_vector = [0.0, 1.0] + [0.0] * 1534

    async with integration_storage(monkeypatch) as storage:
        table = SQLModel.metadata.tables["catalog_item"]
        try:
            await storage.upsert_items([item(namespace, external_id, original_vector)])
            assert storage.engine is not None
            async with storage.engine.connect() as connection:
                original_id = (
                    await connection.execute(
                        select(table.c.id).where(
                            table.c.namespace == namespace,
                            table.c.external_id == external_id,
                        )
                    )
                ).scalar_one()

            updated_attributes = {
                "store": "integration",
                "brand": "updated",
                "unit": "box",
                "pack_size": 2,
                "price": 20,
            }
            await storage.upsert_items(
                [
                    item(
                        namespace,
                        external_id,
                        updated_vector,
                        title="Updated title",
                        body="Updated body",
                        attributes=updated_attributes,
                    )
                ]
            )

            async with storage.engine.connect() as connection:
                row = (
                    await connection.execute(
                        select(
                            table.c.id,
                            table.c.title,
                            table.c.body,
                            table.c.attributes,
                            table.c.embedding,
                        ).where(
                            table.c.namespace == namespace,
                            table.c.external_id == external_id,
                        )
                    )
                ).one()
                count = (
                    await connection.execute(
                        select(func.count())
                        .select_from(table)
                        .where(
                            table.c.namespace == namespace,
                            table.c.external_id == external_id,
                        )
                    )
                ).scalar_one()

            assert count == 1
            assert row.id == original_id
            assert row.title == "Updated title"
            assert row.body == "Updated body"
            assert row.attributes == updated_attributes
            assert row.embedding == updated_vector
        finally:
            await delete_items(storage, namespace, [external_id])


@pytest.mark.asyncio
async def test_knn_orders_results_and_isolates_namespace(monkeypatch):
    token = uuid4().hex
    namespace = f"integration-knn-{token}"
    other_namespace = f"integration-knn-other-{token}"
    external_ids = [
        f"integration-knn-near-{token}",
        f"integration-knn-far-{token}",
        f"integration-knn-other-{token}",
    ]
    near = [1.0] + [0.0] * 1535
    far = [0.0, 1.0] + [0.0] * 1534
    monkeypatch.setitem(
        FILTER_SCHEMAS,
        namespace,
        FILTER_SCHEMAS["restaurant-supplies"],
    )

    async with integration_storage(monkeypatch) as storage:
        try:
            await storage.upsert_items(
                [
                    item(namespace, external_ids[0], near),
                    item(namespace, external_ids[1], far),
                    item(other_namespace, external_ids[2], near),
                ]
            )

            results = await storage.knn_search(
                namespace,
                near,
                filters={"brand": "integration"},
                k=10,
            )

            assert [row["external_id"] for row in results] == external_ids[:2]
            assert all(row["namespace"] == namespace for row in results)
            assert all("embedding" not in row for row in results)
        finally:
            await delete_items(storage, namespace, external_ids[:2])
            await delete_items(storage, other_namespace, external_ids[2:])
