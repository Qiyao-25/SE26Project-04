from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "dev"
    version: str = "0.1.0"
    database_url: str = "sqlite:///./data/dev.db"
    echo_sql: bool = False
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # OpenAI-compatible LLM（解析摘要 / 智能问答共用）
    llm_api_key: str = ""
    llm_api_base: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-v4-flash"
    # 兼容旧环境变量名（将逐步弃用）
    deepseek_api_key: str = ""
    deepseek_api_base: str = ""
    deepseek_model: str = ""

    parse_agent_enabled: bool = True
    parse_agent_max_pages: int = 12
    parse_agent_timeout_s: float = 90.0
    qa_agent_enabled: bool = True
    qa_agent_timeout_s: float = 90.0
    qa_agent_top_k: int = 5
    search_agent_enabled: bool = True
    search_agent_timeout_s: float = 45.0

    model_config = SettingsConfigDict(
        env_prefix="PAPERMATE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _merge_legacy_llm_settings(self):
        """兼容 PAPERMATE_DEEPSEEK_* 旧变量名。"""
        if not self.llm_api_key.strip() and self.deepseek_api_key.strip():
            self.llm_api_key = self.deepseek_api_key.strip()
        if self.deepseek_api_base.strip():
            self.llm_api_base = self.deepseek_api_base.strip()
        if self.deepseek_model.strip():
            self.llm_model = self.deepseek_model.strip()
        return self

    @property
    def parse_agent_ready(self) -> bool:
        return bool(self.parse_agent_enabled and self.llm_api_key.strip())

    @property
    def qa_agent_ready(self) -> bool:
        return bool(self.qa_agent_enabled and self.llm_api_key.strip())

    @property
    def search_agent_ready(self) -> bool:
        return bool(self.search_agent_enabled and self.llm_api_key.strip())

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
