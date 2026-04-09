"""rename registered_by_id to recorded_by_id in delays

Revision ID: e4a1f9c2b3d5
Revises: 969182b2d57f
Create Date: 2026-04-08 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4a1f9c2b3d5'
down_revision: Union[str, Sequence[str], None] = '969182b2d57f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Renomeia registered_by_id → recorded_by_id na tabela delays.

    Motivo: atrasos podem ser registrados por porteiros E coordenadores,
    então o nome genérico 'recorded_by' é mais adequado do que 'registered_by'.
    """
    # 1. Remover FK existente antes de renomear a coluna
    op.drop_constraint(
        'delays_registered_by_id_fkey',
        'delays',
        type_='foreignkey',
    )

    # 2. Renomear a coluna
    op.alter_column(
        'delays',
        'registered_by_id',
        new_column_name='recorded_by_id',
    )

    # 3. Recriar a FK com o novo nome de coluna
    op.create_foreign_key(
        'delays_recorded_by_id_fkey',
        'delays',
        'users',
        ['recorded_by_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Reverte recorded_by_id → registered_by_id."""
    op.drop_constraint(
        'delays_recorded_by_id_fkey',
        'delays',
        type_='foreignkey',
    )

    op.alter_column(
        'delays',
        'recorded_by_id',
        new_column_name='registered_by_id',
    )

    op.create_foreign_key(
        'delays_registered_by_id_fkey',
        'delays',
        'users',
        ['registered_by_id'],
        ['id'],
        ondelete='SET NULL',
    )
