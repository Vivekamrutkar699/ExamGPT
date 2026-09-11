import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database.base_class import Base


class StudyPlan(Base):
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subject.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    schedule: Mapped[dict] = mapped_column(
        JSON, 
        nullable=False  # contains daily, weekly tasks & progression rates
    )
    start_date: Mapped[datetime] = mapped_column(
        DateTime, 
        nullable=False
    )
    end_date: Mapped[datetime] = mapped_column(
        DateTime, 
        nullable=False
    )
