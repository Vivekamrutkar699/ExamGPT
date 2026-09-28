import uuid
from pydantic import BaseModel, ConfigDict, Field


class SubjectBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    semester: int = Field(..., ge=1, le=8)
    branch: str = Field(..., min_length=1, max_length=100)


class SubjectCreate(SubjectBase):
    pass


class SubjectOut(SubjectBase):
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
