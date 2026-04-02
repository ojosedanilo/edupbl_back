from datetime import date, datetime, time
from enum import IntEnum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class Weekday(IntEnum):
    SUNDAY = 1
    MONDAY = 2
    TUESDAY = 3
    WEDNESDAY = 4
    THURSDAY = 5
    FRIDAY = 6
    SATURDAY = 7


# Representa um período da grade (aula ou intervalo)
class Period(BaseModel):
    # Tipo do período:
    # - class_period → aula
    type: Literal['class_period', 'snack_break', 'lunch_break'] = (
        'class_period'
    )

    # Número da aula (None para intervalos)
    period_number: Optional[int] = None

    # Horário de início
    start: time

    # Horário de término
    end: time

    model_config = {
        'frozen': True  # torna hashable
    }

    def contains(self, check_time: time) -> bool:
        """
        Verifica se check_time está dentro do período.
        Baseado na lógica de overlap (um ponto é um intervalo de duração zero).
        """
        if self.start <= self.end:
            # Caso padrão: 08:00 às 10:00
            return self.start <= check_time < self.end
        else:
            # Caso meia-noite: 23:00 às 01:00
            # Está contido se for DEPOIS das 23:00 OU ANTES das 01:00
            return check_time >= self.start or check_time < self.end


# Wrapper para lista de períodos (útil para respostas de API)
class PeriodsList(BaseModel):
    periods: list[Period]


class SlotCreate(BaseModel):
    type: str
    title: str
    classroom_id: int
    teacher_id: int | None
    weekday: Weekday
    period_number: int | None


class SlotPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    title: str
    classroom_id: int
    teacher_id: int | None
    weekday: Weekday
    period_number: int | None


class SlotList(BaseModel):
    slots: list[SlotPublic]


class OverrideCreate(BaseModel):
    title: str
    override_date: date
    starts_at: time
    ends_at: time
    affects_all: bool = True
    classroom_ids: list | None = None
    model_config = ConfigDict(from_attributes=True)


class OverridePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    override_date: date
    starts_at: time
    ends_at: time
    affects_all: bool = True
    # Default None permite model_validate() sem erro;
    # o router sobrepõe via model_copy().
    classroom_ids: list | None = None
    created_at: datetime


class OverrideList(BaseModel):
    overrides: list[OverridePublic]
