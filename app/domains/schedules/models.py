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

from app.domains.schedules.enums import PeriodTypeEnum, WeekdayEnum
from app.shared.db.registry import mapper_registry


@mapped_as_dataclass(mapper_registry)
class ScheduleSlot:
    __tablename__ = 'schedule_slots'

    id: Mapped[int] = mapped_column(
        init=False, primary_key=True, nullable=False
    )

    # Tipo de período
    type: Mapped[PeriodTypeEnum] = mapped_column(
        Enum(
            PeriodTypeEnum,
            name='period_type',
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
    )

    # Nome do período
    title: Mapped[str] = mapped_column(String(200), nullable=False)

    # IDs da sala e do professor
    # classroom_id é NULL para slots que pertencem ao professor e não a uma
    # turma específica (ex: planejamento e folga do professor).
    classroom_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('classrooms.id', ondelete='CASCADE'), nullable=True
    )
    teacher_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )

    # Dia da semana
    weekday: Mapped[WeekdayEnum] = mapped_column(
        Enum(WeekdayEnum, name='weekday'), nullable=False
    )

    # Número do período
    period_number: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Restrições de unicidade:
    #
    # 1. Slots de turma (classroom_id NOT NULL):
    #    Uma turma não pode ter dois slots do mesmo tipo no mesmo dia/período.
    #    Ex: não pode ter dois class_period diferentes no mesmo horário.
    #
    # 2. Slots de professor (classroom_id IS NULL, teacher_id NOT NULL):
    #    Um professor não pode ter dois slots de planejamento/folga no mesmo dia/período.
    #    Implementado como UniqueConstraint filtrado via Index com postgresql_where
    #    para garantir que NULLs não conflitem entre professores distintos.
    __table_args__ = (
        # Unicidade para slots de turma (classroom_id preenchido)
        UniqueConstraint(
            'classroom_id',
            'weekday',
            'period_number',
            'type',
            name='uq_classroom_weekday_period',
        ),
        # Unicidade para slots de professor (classroom_id NULL)
        UniqueConstraint(
            'teacher_id',
            'weekday',
            'period_number',
            'type',
            name='uq_teacher_weekday_period',
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

    # Professor (ou coordenador) responsável por cobrir este horário.
    # Quando preenchido, o override representa um professor específico
    # assumindo uma aula — útil para sobrepor o horário regular de uma turma.
    # NULL = override genérico de horário (sem professor associado).
    teacher_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        default=None,
    )

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
