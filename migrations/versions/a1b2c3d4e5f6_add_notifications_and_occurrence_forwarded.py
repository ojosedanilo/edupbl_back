"""add_notifications_and_occurrence_forwarded

Revision ID: a1b2c3d4e5f6
Revises: 969182b2d57f
Create Date: 2026-04-09 22:00:00.000000

Mudanças:
  - Cria a tabela `notifications` (in-app notifications por usuário)
  - Adiciona coluna `forwarded_to_coordinator` em `occurrences`
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '969182b2d57f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Tabela notifications ─────────────────────────────────────────── #
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column(
            'recipient_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('action_url', sa.String(length=500), nullable=True),
        sa.Column(
            'is_read',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            'created_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_notifications_recipient_id',
        'notifications',
        ['recipient_id'],
    )
    op.create_index(
        'ix_notifications_is_read',
        'notifications',
        ['is_read'],
    )

    # ── Coluna forwarded_to_coordinator em occurrences ───────────────── #
    op.add_column(
        'occurrences',
        sa.Column(
            'forwarded_to_coordinator',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column('occurrences', 'forwarded_to_coordinator')
    op.drop_index('ix_notifications_is_read', table_name='notifications')
    op.drop_index('ix_notifications_recipient_id', table_name='notifications')
    op.drop_table('notifications')
