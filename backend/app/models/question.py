import uuid
from sqlalchemy import Text, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database.base_class import Base


class Question(Base):
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
    text: Mapped[str] = mapped_column(
        Text, 
        nullable=False
    )
    marks_weight: Mapped[int] = mapped_column(
        Integer, 
        nullable=False  # 2, 5, 10, 15
    )
    unit_tag: Mapped[str] = mapped_column(
        String(100), 
        nullable=True
    )
    chapter: Mapped[str] = mapped_column(
        String(255), 
        nullable=True
    )
    is_pyq: Mapped[bool] = mapped_column(
        Boolean, 
        default=False, 
        nullable=False
    )
    occurrences: Mapped[int] = mapped_column(
        Integer, 
        default=1, 
        nullable=False
    )
