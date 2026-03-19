"""add_user_theme

Revision ID: ac860c93cc2e
Revises: 9b3e1f2c4d8a
Create Date: 2026-03-19 16:53:17.097577

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ac860c93cc2e'
down_revision: Union[str, Sequence[str], None] = '9b3e1f2c4d8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('theme', sa.String(32), nullable=False, server_default='macchiato'))


def downgrade() -> None:
    op.drop_column('users', 'theme')
