import uuid
from datetime import datetime

from pgvector.sqlalchemy import VECTOR
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel


class Turn(SQLModel, table=True):
    __tablename__ = "turn"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "seq",
            name="uq_turn_session_id_seq",
        ),
        Index(
            "ix_turn_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_turn_subject_id", "subject_id"),
    )

    # Turn is append-only by discipline, not by a technical constraint; this keeps
    # the log reproducible when embeddings are rebuilt.
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            default=uuid.uuid4,
        ),
    )
    subject_id: str = Field(sa_column=Column(Text, nullable=False))
    session_id: str = Field(sa_column=Column(Text, nullable=False))
    seq: int = Field(sa_column=Column(Integer, nullable=False))
    ts: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    user_text: str = Field(sa_column=Column(Text, nullable=False))
    assistant_text: str = Field(sa_column=Column(Text, nullable=False))
    embedding: list[float] = Field(
        sa_column=Column(VECTOR(1536), nullable=False),
    )


class Fragment(BaseModel):
    """A similarity hit with its neighboring turns."""

    turns: list[Turn]
    session_id: str
    ts: datetime
    similarity: float
