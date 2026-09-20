from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.catalog_item import CatalogItem


def test_catalog_item_matches_the_canonical_schema():
    table = CatalogItem.__table__

    assert table.name == "catalog_item"
    assert set(table.columns) == {
        table.c.id,
        table.c.namespace,
        table.c.external_id,
        table.c.title,
        table.c.body,
        table.c.attributes,
        table.c.embedding,
    }
    assert isinstance(table.c.id.type, UUID)
    assert table.c.id.primary_key and not table.c.id.nullable
    assert isinstance(table.c.attributes.type, JSONB)
    assert not table.c.attributes.nullable
    assert isinstance(table.c.embedding.type, VECTOR)
    assert table.c.embedding.type.dim == 1536
    assert not table.c.embedding.nullable
    assert all(
        not table.c[name].nullable
        for name in ("namespace", "external_id", "title", "body")
    )

    constraint = next(
        item
        for item in table.constraints
        if item.name == "uq_catalog_item_namespace_external_id"
    )
    assert [column.name for column in constraint.columns] == [
        "namespace",
        "external_id",
    ]

    index = next(
        item for item in table.indexes if item.name == "ix_catalog_item_embedding_hnsw"
    )
    assert index.dialect_options["postgresql"]["using"] == "hnsw"
    assert index.dialect_options["postgresql"]["ops"] == {
        "embedding": "vector_cosine_ops"
    }


def test_catalog_item_defaults_are_application_side():
    item = CatalogItem(
        namespace="restaurant-supplies",
        external_id="sku-1",
        title="Salt",
        body="Fine salt",
        embedding=[0.0] * 1536,
    )

    assert item.id is not None
    assert item.attributes == {}
