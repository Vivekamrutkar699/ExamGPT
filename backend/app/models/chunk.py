import uuid
from sqlalchemy import Text, Integer, String, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database.base_class import Base


class Chunk(Base):
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer, 
        nullable=False
    )
    content: Mapped[str] = mapped_column(
        Text, 
        nullable=False
    )
    section_title: Mapped[str] = mapped_column(
        String(255), 
        nullable=True
    )
    unit_tag: Mapped[str] = mapped_column(
        String(100), 
        nullable=True  # e.g., "Unit 1", "Unit 2"
    )
    metadata_json: Mapped[dict] = mapped_column(
        JSON, 
        nullable=True  # holds coordinate layouts, page numbers, confidence
    )
