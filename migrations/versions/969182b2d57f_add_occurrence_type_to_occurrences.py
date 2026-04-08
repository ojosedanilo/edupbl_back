"""add occurrence_type to occurrences

Revision ID: 969182b2d57f
Revises: a3f2c1d8e9b0
Create Date: 2026-04-08 18:49:34.256563
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '969182b2d57f'
down_revision: Union[str, Sequence[str], None] = 'a3f2c1d8e9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --- ENUM ---
occurrence_type_enum = sa.Enum(
    'INDISCIPLINA',
    'CELULAR',
    'DESRESPEITO',
    'RENDIMENTO',
    'ATRASOS',
    'FALTAS',
    'OUTROS',
    name='occurrence_type'
)


def upgrade() -> None:
    """Upgrade schema."""
    
    bind = op.get_bind()

    # 1. Criar enum explicitamente
    occurrence_type_enum.create(bind, checkfirst=True)

    # 2. Criar tabela delays
    op.create_table(
        'delays',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('arrival_time', sa.Time(), nullable=False),
        sa.Column('delay_minutes', sa.Integer(), nullable=False),
        sa.Column('registered_by_id', sa.Integer(), nullable=True),
        sa.Column('approved_by_id', sa.Integer(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('delay_date', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=False),
        sa.Column('expected_time', sa.Time(), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'APPROVED', 'REJECTED', name='delay_status'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['approved_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['registered_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 3. Adicionar coluna com default temporário (evita erro com dados existentes)
    op.add_column(
        'occurrences',
        sa.Column(
            'occurrence_type',
            occurrence_type_enum,
            nullable=False,
            server_default='OUTROS'
        )
    )

    # 4. Remover default
    op.alter_column(
        'occurrences',
        'occurrence_type',
        server_default=None
    )

    # 5. Nova coluna opcional
    op.add_column(
        'occurrences',
        sa.Column('occurred_at', sa.DateTime(), nullable=True)
    )

    # 6. schedule_overrides
    op.add_column(
        'schedule_overrides',
        sa.Column('teacher_id', sa.Integer(), nullable=True)
    )

    op.create_foreign_key(
        'fk_schedule_overrides_teacher_id_users',
        'schedule_overrides',
        'users',
        ['teacher_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    """Downgrade schema."""
    
    bind = op.get_bind()

    # 1. Remover FK
    op.drop_constraint(
        'fk_schedule_overrides_teacher_id_users',
        'schedule_overrides',
        type_='foreignkey'
    )

    # 2. Remover coluna teacher_id
    op.drop_column('schedule_overrides', 'teacher_id')

    # 3. Remover colunas de occurrences
    op.drop_column('occurrences', 'occurred_at')
    op.drop_column('occurrences', 'occurrence_type')

    # 4. Remover tabela delays
    op.drop_table('delays')

    # 5. Remover enum
    occurrence_type_enum.drop(bind, checkfirst=True)