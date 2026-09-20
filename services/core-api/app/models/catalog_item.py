import uuid
from typing import Any

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import Column, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlmodel import Field, SQLModel


class CatalogItem(SQLModel, table=True):
    __tablename__ = "catalog_item"
    __table_args__ = (
        UniqueConstraint(
            "namespace",
            "external_id",
            name="uq_catalog_item_namespace_external_id",
        ),
        Index(
            "ix_catalog_item_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            default=uuid.uuid4,
        ),
    )
    namespace: str = Field(sa_column=Column(Text, nullable=False))
    external_id: str = Field(sa_column=Column(Text, nullable=False))
    title: str = Field(sa_column=Column(Text, nullable=False))
    body: str = Field(sa_column=Column(Text, nullable=False))
    attributes: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False),
    )
    embedding: list[float] = Field(
        sa_column=Column(VECTOR(1536), nullable=False),
    )
