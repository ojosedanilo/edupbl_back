from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import Date, Enum, ForeignKey, Integer, Text, Time, func
from sqlalchemy.orm import Mapped, mapped_as_dataclass, mapped_column

from app.domains.delays.enums import DelayStatusEnum
from app.shared.db.registry import mapper_registry


@mapped_as_dataclass(mapper_registry)
class Delay:
    __tablename__ = 'delays'

    id: Mapped[int] = mapped_column(
        init=False, primary_key=True, nullable=False
    )

    # Atraso some se aluno for deletado
    student_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
    )
    # Hora que o aluno chegou — obrigatória, informada por quem registra
    arrival_time: Mapped[time] = mapped_column(Time, nullable=False)
    # Calculado automaticamente ao registrar (em minutos)
    delay_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Quem registrou o atraso (porteiro, coordenador etc.) — fica se deletado
    recorded_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        default=None,
    )
    # Preenchido só ao aprovar/rejeitar
    approved_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        default=None,
    )

    # Motivo informado pelo aluno/registrador (opcional)
    reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None
    )
    # Motivo da rejeição (preenchido pela coordenação)
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None
    )

    # Data do atraso — obrigatória (padrão: hoje), limitada aos últimos 3 dias
    delay_date: Mapped[date] = mapped_column(
        Date,
        default=date.today,
        server_default=func.current_date(),
    )
    # Hora esperada para a chegada (calculada com base nos períodos)
    expected_time: Mapped[time] = mapped_column(
        Time, init=False, default=time(7, 30)
    )
    # Situação da entrada do aluno atrasado (pendente, aprovado, rejeitado)
    status: Mapped[DelayStatusEnum] = mapped_column(
        Enum(DelayStatusEnum, name='delay_status'),
        init=False,
        default=DelayStatusEnum.PENDING,
    )

    # Metadados
    created_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now(), onupdate=func.now()
    )
