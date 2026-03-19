"""thread_policy_name

Revision ID: 9b3e1f2c4d8a
Revises: 7ac692c4c515
Create Date: 2026-03-19

Add optional human-readable name to thread_policies.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '9b3e1f2c4d8a'
down_revision = '7ac692c4c515'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('thread_policies', sa.Column('name', sa.String(256), nullable=True))


def downgrade() -> None:
    op.drop_column('thread_policies', 'name')
