"""create weekday enum

Revision ID: f7623a4587d2
Revises: d1596f76447a
Create Date: 2026-04-04 10:58:12.436674

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import ENUM

weekday_enum = ENUM(
    'SUNDAY', 'MONDAY', 'TUESDAY', 'WEDNESDAY',
    'THURSDAY', 'FRIDAY', 'SATURDAY',
    name='weekday'
)


# revision identifiers, used by Alembic.
revision: str = 'f7623a4587d2'
down_revision: Union[str, Sequence[str], None] = 'd1596f76447a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.
"""
    weekday_enum.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    """Downgrade schema.
"""
    weekday_enum.drop(op.get_bind(), checkfirst=True)
