"""merge

Revision ID: 010981d7ac25
Revises: 988abdae889e
Create Date: 2026-04-09 22:38:20.038040

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '010981d7ac25'
down_revision: Union[str, Sequence[str], None] = '988abdae889e'
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
