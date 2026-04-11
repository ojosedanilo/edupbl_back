"""schedule_slots: classroom_id nullable, constraint de professor

Revision ID: a1b2c3d4e5f6
Revises: 62673cf35b89
Create Date: 2026-04-11 20:00:00.000000

Mudanças
--------
1. ``schedule_slots.classroom_id`` passa de NOT NULL para NULL.
   Slots de planejamento e folga pertencem ao professor, não a uma turma,
   portanto não têm sala associada.

2. Adiciona UniqueConstraint ``uq_teacher_weekday_period`` em
   (teacher_id, weekday, period_number, type) para garantir que um
   professor não tenha dois slots do mesmo tipo no mesmo dia/período.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '62673cf35b89'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Torna classroom_id nullable
    op.alter_column(
        'schedule_slots',
        'classroom_id',
        existing_type=sa.Integer(),
        nullable=True,
    )

    # 2. Adiciona constraint de unicidade por professor
    op.create_unique_constraint(
        'uq_teacher_weekday_period',
        'schedule_slots',
        ['teacher_id', 'weekday', 'period_number', 'type'],
    )


def downgrade() -> None:
    # Remove constraint de professor
    op.drop_constraint(
        'uq_teacher_weekday_period',
        'schedule_slots',
        type_='unique',
    )

    # Reverte classroom_id para NOT NULL
    # Atenção: falhará se houver linhas com classroom_id NULL no banco.
    # Limpe os slots de planning/free antes de fazer downgrade.
    op.alter_column(
        'schedule_slots',
        'classroom_id',
        existing_type=sa.Integer(),
        nullable=False,
    )
