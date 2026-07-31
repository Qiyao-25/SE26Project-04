from sqlalchemy.engine import Engine

from app.core.config import Settings
from app.repository.health import check_database
from app.schema.common import HealthData


def get_health(engine: Engine, settings: Settings) -> HealthData:
    database = check_database(engine)
    return HealthData(
        status="ok" if database == "ok" else "degraded",
        database=database,
        environment=settings.environment,
        version=settings.version,
        component_versions={"api": settings.version, "service": settings.version, "orm": "sqlalchemy-2", "migration": "alembic-1"},
    )

