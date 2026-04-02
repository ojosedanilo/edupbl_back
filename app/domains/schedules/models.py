from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Table,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_as_dataclass, mapped_column

from app.domains.schedules.schemas import Weekday
from app.shared.db.registry import mapper_registry


@mapped_as_dataclass(mapper_registry)
class ScheduleSlot:
    __tablename__ = 'schedule_slots'

    id: Mapped[int] = mapped_column(
        init=False, primary_key=True, nullable=False
    )

    # Tipo de período
    type: Mapped[str] = mapped_column(
        Enum('class_period', 'snack_break', 'lunch_break', name='period_type'),
        nullable=False,
    )

    # Nome do período
    title: Mapped[str] = mapped_column(String(200), nullable=False)

    # IDs da sala e do professor
    classroom_id: Mapped[int] = mapped_column(
        ForeignKey('classrooms.id', ondelete='CASCADE'), nullable=False
    )
    teacher_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )

    # Dia da semana
    weekday: Mapped[Weekday] = mapped_column(nullable=False)

    # Número do período
    period_number: Mapped[Optional[int]] = mapped_column(nullable=True)

    # uma turma não pode ter dois professores no mesmo período do mesmo dia
    __table_args__ = (
        UniqueConstraint(
            'classroom_id',
            'weekday',
            'period_number',
            'type',
            name='uq_classroom_weekday_period',
        ),
    )


@mapped_as_dataclass(mapper_registry)
class ScheduleOverride:
    __tablename__ = 'schedule_overrides'

    id: Mapped[int] = mapped_column(
        init=False, primary_key=True, nullable=False
    )

    # Nome do período
    title: Mapped[str] = mapped_column(String(200), nullable=False)

    # Data específica do evento
    override_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Início e final do horário modificado
    starts_at: Mapped[time] = mapped_column(Time, nullable=False)
    ends_at: Mapped[time] = mapped_column(Time, nullable=False)

    # True = toda a escola; False = só turmas definidas
    affects_all: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # Metadados
    created_at: Mapped[datetime] = mapped_column(
        DateTime, init=False, server_default=func.now()
    )


# Tabela de associação entre ID da sala e ID do agendamento de substituição
override_classrooms = Table(
    'override_classrooms',
    mapper_registry.metadata,
    Column(
        'classroom_id',
        Integer,
        ForeignKey('classrooms.id', ondelete='CASCADE'),
        primary_key=True,
    ),
    Column(
        'override_id',
        Integer,
        ForeignKey('schedule_overrides.id', ondelete='CASCADE'),
        primary_key=True,
    ),
)
