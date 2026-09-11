import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database.base_class import Base


class Document(Base):
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subject.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(
        String(255), 
        nullable=False
    )
    storage_path: Mapped[str] = mapped_column(
        String(500), 
        nullable=False
    )
    file_type: Mapped[str] = mapped_column(
        String(20), 
        nullable=False
    )
    category: Mapped[str] = mapped_column(
        String(50), 
        nullable=False  # notes, pyq, book, lab
    )
    processing_status: Mapped[str] = mapped_column(
        String(50), 
        default="pending",  # pending, processing, completed, failed
        nullable=False
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        nullable=False
    )
