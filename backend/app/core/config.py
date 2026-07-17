from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "dev"
    version: str = "0.1.0"
    database_url: str = "sqlite:///./data/dev.db"
    echo_sql: bool = False
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # DeepSeek Summarize Agent（解析任务后台执行）
    deepseek_api_key: str = ""
    deepseek_api_base: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    parse_agent_enabled: bool = True
    parse_agent_max_pages: int = 12
    parse_agent_timeout_s: float = 90.0

    model_config = SettingsConfigDict(
        env_prefix="PAPERMATE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def parse_agent_ready(self) -> bool:
        return bool(self.parse_agent_enabled and self.deepseek_api_key.strip())

    @property
    def is_test(self) -> bool:
        return self.environment == "test"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


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

