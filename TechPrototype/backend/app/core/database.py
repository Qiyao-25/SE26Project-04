from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, ensure_sqlite_parent


def create_engine_for(settings: Settings) -> Engine:
    ensure_sqlite_parent(settings.database_url)
    is_sqlite = settings.database_url.startswith("sqlite")
    connect_args = {"check_same_thread": False, "timeout": 5} if is_sqlite else {}
    engine_options = {
        "echo": settings.echo_sql,
        "connect_args": connect_args,
        "pool_size": max(1, int(settings.db_pool_size)),
        "max_overflow": max(0, int(settings.db_max_overflow)),
        "pool_timeout": max(0.1, float(settings.db_pool_timeout_s)),
        # SQLite has no stale network connections. Avoid an extra probe query
        # for every checkout; retain it for networked database connections.
        "pool_pre_ping": not is_sqlite,
    }
    if settings.database_url == "sqlite:///:memory:":
        engine_options["poolclass"] = StaticPool
        for key in ("pool_size", "max_overflow", "pool_timeout"):
            engine_options.pop(key, None)
    return create_engine(settings.database_url, **engine_options)


def get_db(engine: Engine) -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
