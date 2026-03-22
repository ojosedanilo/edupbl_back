from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OccurrenceCreate(BaseModel):
    student_id: int
    title: str
    description: str


class OccurrenceUpdate(BaseModel):
    """Atualização parcial — todos os campos são opcionais."""

    student_id: int | None = None
    title: str | None = None
    description: str | None = None


class OccurrencePublic(BaseModel):
    id: int
    created_by_id: int | None
    student_id: int
    title: str
    description: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OccurrenceList(BaseModel):
    occurrences: list[OccurrencePublic]
