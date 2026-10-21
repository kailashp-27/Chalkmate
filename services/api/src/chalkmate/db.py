from functools import lru_cache

from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import DeclarativeBase

from chalkmate.config import get_settings


class Base(DeclarativeBase):
    metadata = MetaData(
        schema="chalkmate",
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        },
    )


@lru_cache
def get_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True, hide_parameters=True)


def set_identity(session, user_id: str, email: str):
    session.execute(
        text("SELECT set_config('app.user_id', :id, true), set_config('app.email', :email, true)"),
        {"id": user_id, "email": email},
    )
