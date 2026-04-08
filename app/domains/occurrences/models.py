"""
Model SQLAlchemy da tabela `occurrences`.

Nota sobre relacionamentos:
  Este model não declara relationship() intencionalmente.
  O bug do SQLAlchemy 2.x com mapped_as_dataclass causa um problema:
  após session.refresh(), um relationship com lazy='noload' e default=None
  sobrescreve o valor da FK escalar em memória, fazendo created_by_id
  virar None no objeto Python mesmo estando correto no banco.

  Como OccurrencePublic usa apenas os campos escalares (student_id,
  created_by_id), os relationships são desnecessários aqui.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_as_dataclass, mapped_column

from app.domains.occurrences.enums import OccurrenceTypeEnum
from app.shared.db.registry import mapper_registry


@mapped_as_dataclass(mapper_registry)
class Occurrence:
    """Ocorrência disciplinar ou informativa sobre um aluno."""

    __tablename__ = 'occurrences'

    id: Mapped[int] = mapped_column(
        init=False, primary_key=True, nullable=False
    )

    # Aluno envolvido — deletar o aluno deleta também suas ocorrências
    student_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Tipo da ocorrência — determina a categoria do problema registrado
    occurrence_type: Mapped[OccurrenceTypeEnum] = mapped_column(
        Enum(OccurrenceTypeEnum, name='occurrence_type'),
        nullable=False,
        default=OccurrenceTypeEnum.OUTROS,
    )

    # Quem registrou (professor/coordenador) — vira NULL se o criador for deletado
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        default=None,
    )

    # Horário em que a ocorrência aconteceu (definido pelo usuário)
    occurred_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        default=None,
    )

    # Metadados
    created_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now(), onupdate=func.now()
    )
