from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "dev"
    version: str = "0.1.0"
    database_url: str = "sqlite:///./data/dev.db"
    echo_sql: bool = False

    model_config = SettingsConfigDict(
        env_prefix="PAPERMATE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_test(self) -> bool:
        return self.environment == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def ensure_sqlite_parent(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return
    database_path = database_url.removeprefix("sqlite:///")
    if database_path in {":memory:", ""}:
        return
    Path(database_path).expanduser().parent.mkdir(parents=True, exist_ok=True)

