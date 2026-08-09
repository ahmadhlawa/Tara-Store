"""Alembic environment. The database URL always comes from application settings."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

from app.core.config import settings
from app.db.base import metadata_with_models
from app.db.session import build_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata_with_models()


def run_migrations_offline() -> None:
    context.configure(
        url=settings.sqlalchemy_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = build_engine(settings.sqlalchemy_url())
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite cannot ALTER most things in place; batch mode rewrites tables.
            render_as_batch=connection.dialect.name == "sqlite",
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
