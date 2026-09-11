import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class StudyPlanCreate(BaseModel):
    subject_id: uuid.UUID
    days_duration: int = Field(30, ge=7, le=120)


class StudyPlanUpdate(BaseModel):
    schedule: Dict[str, Any]


class StudyPlanOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    subject_id: uuid.UUID
    schedule: Dict[str, Any]
    start_date: datetime
    end_date: datetime

    class Config:
        from_attributes = True
