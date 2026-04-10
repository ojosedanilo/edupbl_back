"""merge

Revision ID: 988abdae889e
Revises: a1b2c3d4e5f6, e4a1f9c2b3d5
Create Date: 2026-04-09 22:38:04.112854

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '988abdae889e'
down_revision: Union[str, Sequence[str], None] = ('a1b2c3d4e5f6', 'e4a1f9c2b3d5')
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
