from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings, ensure_sqlite_parent


def create_engine_for(settings: Settings) -> Engine:
    ensure_sqlite_parent(settings.database_url)
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, echo=settings.echo_sql, connect_args=connect_args, pool_pre_ping=True)


def get_db(engine: Engine) -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

