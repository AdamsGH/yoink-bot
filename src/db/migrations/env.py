from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

from yoink.storage.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    """
    Read DATABASE_URL from environment and convert to a sync psycopg2 URL
    so Alembic can use it without asyncpg.
    """
    url = os.environ.get("DATABASE_URL", "postgresql+psycopg2://yoink:yoink@localhost:5432/yoink")
    # Swap async driver for sync driver
    url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    url = url.replace("postgresql://", "postgresql+psycopg2://")
    return url


def run_migrations_offline() -> None:
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _render_item(type_: str, obj: object, autogen_context: object) -> str | bool:
    """Inject server_default for NOT NULL Boolean columns added to existing tables.

    Without a server_default, ALTER TABLE ... ADD COLUMN <bool> NOT NULL fails
    on PostgreSQL when the table already has rows. Autogenerate never adds this
    automatically, so we inject it here and strip it after the column exists.
    """
    return False  # use default rendering; DDL fixup is done in the migration body


def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = _get_url()
    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Emit COMMENT ON statements for columns/tables (optional, keeps schema docs)
            include_object=lambda obj, name, type_, reflected, compare_to: True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
