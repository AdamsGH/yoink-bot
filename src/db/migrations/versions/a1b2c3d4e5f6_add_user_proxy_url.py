"""add user proxy_url

Revision ID: a1b2c3d4e5f6
Revises: dc8a66b6a71f
Create Date: 2026-03-17 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'dc8a66b6a71f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('proxy_url', sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'proxy_url')
