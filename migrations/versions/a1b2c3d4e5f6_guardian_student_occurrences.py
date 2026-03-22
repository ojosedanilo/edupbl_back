"""Adicionar guardian_student, occurrences e corrigir constraint username

Revision ID: a1b2c3d4e5f6
Revises: 874b6bb98509
Create Date: 2026-03-22 12:00:00.000000

Mudanças:
- Remove ck_users_username_chars (usava operador ~ do PostgreSQL, incompatível com SQLite)
- Adiciona ck_users_username_nonempty (portável)
- Cria tabela guardian_student (many-to-many responsável ↔ aluno)
- Cria tabela occurrences
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '874b6bb98509'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # 1. Corrigir constraint de username                                 #
    # ------------------------------------------------------------------ #
    # Em SQLite, DROP CONSTRAINT não é suportado diretamente.
    # A constraint antiga (ck_users_username_chars) usava `~` (regex do
    # PostgreSQL). Como não é possível remover constraints individuais no
    # SQLite sem recriar a tabela, e a nova constraint é aplicada no
    # banco de produção (PostgreSQL), usamos batch_alter_table para
    # recriar com a constraint correta.
    with op.batch_alter_table('users', schema=None) as batch_op:
        # Remove a constraint antiga se existir (PostgreSQL)
        try:
            batch_op.drop_constraint(
                'ck_users_username_chars', type_='check'
            )
        except Exception:
            pass  # SQLite ou constraint inexistente — ignora

        batch_op.create_check_constraint(
            'ck_users_username_nonempty',
            "length(username) > 0",
        )

    # ------------------------------------------------------------------ #
    # 2. Tabela de associação responsável ↔ aluno                       #
    # ------------------------------------------------------------------ #
    op.create_table(
        'guardian_student',
        sa.Column(
            'guardian_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            'student_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            primary_key=True,
            nullable=False,
        ),
    )

    # ------------------------------------------------------------------ #
    # 3. Tabela occurrences                                              #
    # ------------------------------------------------------------------ #
    op.create_table(
        'occurrences',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            'created_by_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column(
            'student_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table('occurrences')
    op.drop_table('guardian_student')

    with op.batch_alter_table('users', schema=None) as batch_op:
        try:
            batch_op.drop_constraint(
                'ck_users_username_nonempty', type_='check'
            )
        except Exception:
            pass

        batch_op.create_check_constraint(
            'ck_users_username_chars',
            r"username ~ '^[a-z0-9_.]+$'",
        )
