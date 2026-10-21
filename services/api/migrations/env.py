from alembic import context
from sqlalchemy import create_engine, pool

from chalkmate import (
    assessment_models,  # noqa: F401
    followup_models,  # noqa: F401
    intelligence_models,  # noqa: F401
    models,  # noqa: F401 -- registers migration metadata
    operations,  # noqa: F401
    planning_models,  # noqa: F401
    reporting_models,  # noqa: F401
    support_models,  # noqa: F401
)
from chalkmate.config import get_settings
from chalkmate.db import Base

target_metadata = Base.metadata


def include_name(name, type_, parent_names):
    return name == "chalkmate" if type_ == "schema" else True


if context.is_offline_mode():
    context.configure(
        url=get_settings().migration_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(get_settings().migration_database_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
        )
        with context.begin_transaction():
            context.run_migrations()
