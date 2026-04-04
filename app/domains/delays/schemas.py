from datetime import date, datetime, time
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.domains.delays.enums import DelayStatusEnum


class DelayCreate(BaseModel):
    # Campos informados pelo porteiro ao registrar o atraso
    student_id: int
    arrival_time: time
    reason: Optional[str] = None


class DelayApprove(BaseModel):
    # Body usado no endpoint /approve — sem campos adicionais
    pass


class DelayReject(BaseModel):
    # Body usado no endpoint /reject — motivo é obrigatório
    rejection_reason: str


class DelayPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    registered_by_id: Optional[int]
    approved_by_id: Optional[int]
    delay_date: date
    arrival_time: time
    expected_time: time
    delay_minutes: int
    status: DelayStatusEnum
    reason: Optional[str]
    rejection_reason: Optional[str]
    created_at: datetime
    updated_at: datetime


class DelayList(BaseModel):
    delays: list[DelayPublic]
