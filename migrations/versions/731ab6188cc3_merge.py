"""merge

Revision ID: 731ab6188cc3
Revises: 010981d7ac25
Create Date: 2026-04-09 22:39:04.653680

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '731ab6188cc3'
down_revision: Union[str, Sequence[str], None] = '010981d7ac25'
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
