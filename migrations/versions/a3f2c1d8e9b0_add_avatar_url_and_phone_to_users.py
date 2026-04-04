"""add avatar_url and phone to users

Revision ID: a3f2c1d8e9b0
Revises: f7623a4587d2
Create Date: 2026-04-04 17:00:00.000000

Adiciona dois campos opcionais ao model User:
  avatar_url  — caminho relativo do arquivo WebP salvo em data/avatars/
  phone       — telefone para notificações (WhatsApp/SMS), preenchido voluntariamente
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a3f2c1d8e9b0'
down_revision: Union[str, Sequence[str], None] = 'f7623a4587d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('avatar_url', sa.String(length=255), nullable=True),
    )
    op.add_column(
        'users',
        sa.Column('phone', sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'phone')
    op.drop_column('users', 'avatar_url')
