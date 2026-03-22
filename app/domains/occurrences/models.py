from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import (
    Mapped,
    mapped_as_dataclass,
    mapped_column,
)

from app.shared.db.registry import mapper_registry


@mapped_as_dataclass(mapper_registry)
class Occurrence:
    """Ocorrência disciplinar ou informativa sobre um aluno."""

    __tablename__ = 'occurrences'

    id: Mapped[int] = mapped_column(
        init=False, primary_key=True, nullable=False
    )

    # Aluno sobre quem é a ocorrência — CASCADE DELETE
    student_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Quem criou (professor / coordenador) — SET NULL se deletado
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        default=None,
    )

    created_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now(), onupdate=func.now()
    )

    # ------------------------------------------------------------------ #
    # Relacionamentos                                                     #
    # ------------------------------------------------------------------ #
    # Nenhum relationship é mantido neste modelo. O mesmo bug do SQLAlchemy
    # 2.x com mapped_as_dataclass que afetava student (relationship com
    # default=None sobrescrevia a FK no INSERT) também afeta created_by:
    # após session.refresh(), o noload do relationship reseta created_by_id
    # para None em memória. OccurrencePublic usa apenas os campos escalares
    # (created_by_id, student_id), por isso os relationships são desnecessários.
