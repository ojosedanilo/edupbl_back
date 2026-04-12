from datetime import date, datetime, time
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.domains.schedules.enums import PeriodTypeEnum, WeekdayEnum


# Representa um período da grade (aula ou intervalo)
class Period(BaseModel):
    # Tipo do período:
    # - class_period → aula
    type: PeriodTypeEnum = PeriodTypeEnum.CLASS_PERIOD

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
    classroom_id: int | None  # None para slots PLANNING e FREE
    teacher_id: int | None
    weekday: WeekdayEnum
    period_number: int | None


class SlotPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    title: str
    classroom_id: int | None  # None para slots PLANNING e FREE
    teacher_id: int | None
    weekday: WeekdayEnum
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
    # Professor/coordenador que cobre este horário (opcional)
    teacher_id: int | None = None
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
    # Professor/coordenador associado ao override (None = genérico)
    teacher_id: int | None = None
    created_at: datetime


class OverrideList(BaseModel):
    overrides: list[OverridePublic]


# ── Schemas de professores (visão reduzida, sem dados sensíveis) ─────────── #


class TeacherSummary(BaseModel):
    """Perfil mínimo de professor para exibição na grade de horários."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    classroom_id: int | None = None


class TeacherSummaryList(BaseModel):
    teachers: list[TeacherSummary]


# ── Schemas de bulk ──────────────────────────────────────────────────────── #


class BulkClassroomsResponse(BaseModel):
    """Slots agrupados por classroom_id. Apenas turmas com acesso autorizado."""

    slots_by_classroom: dict[int, list[SlotPublic]]


class BulkTeachersResponse(BaseModel):
    """Slots agrupados por teacher_id."""

    slots_by_teacher: dict[int, list[SlotPublic]]


class BulkOverridesResponse(BaseModel):
    """
    Overrides relevantes para o conjunto de turmas/professores pedido.
    Inclui todos os overrides affects_all=True e os que tenham ao menos
    uma das classroom_ids ou teacher_ids solicitados.
    """

    overrides: list[OverridePublic]
