"""merge

Revision ID: 52ecdef5caed
Revises: 731ab6188cc3
Create Date: 2026-04-09 22:56:43.713972

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '52ecdef5caed'
down_revision: Union[str, Sequence[str], None] = '731ab6188cc3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.
"""
    pass


def downgrade() -> None:
    """Downgrade schema.
"""
    pass
