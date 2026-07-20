from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    environment: str = "dev"
    version: str = "0.1.0"
    database_url: str = "sqlite:///./data/dev.db"
    echo_sql: bool = False
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    agent_enabled: bool | None = None
    agent_api_key: str | None = None
    agent_model: str = ""
    agent_base_url: str = "https://api.openai.com/v1"
    agent_timeout_s: float = 30.0
    worker_token: str = ""
    auth_secret: str = "papermate-dev-secret"

    # Unified OpenAI-compatible LLM configuration.
    llm_api_key: str = ""
    llm_api_base: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-v4-flash"
    # Compatibility names accepted during the migration from AGENT_* settings.
    deepseek_api_key: str = ""
    deepseek_api_base: str = ""
    deepseek_model: str = ""
    parse_agent_enabled: bool = True
    parse_agent_max_pages: int = 12
    parse_agent_timeout_s: float = 90.0
    qa_agent_enabled: bool = True
    qa_agent_timeout_s: float = 90.0
    qa_agent_top_k: int = 8
    qa_agent_evidence_chars: int = 1400
    search_agent_enabled: bool = True
    search_agent_timeout_s: float = 45.0
    graph_agent_enabled: bool = True
    graph_agent_timeout_s: float = 60.0
    assist_agent_enabled: bool = True
    assist_agent_timeout_s: float = 60.0
    # Scheduled arXiv subscription crawl (Demo)
    crawl_enabled: bool = True
    crawl_interval_s: int = 21600  # 6 hours

    model_config = SettingsConfigDict(
        env_prefix="PAPERMATE_",
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def merge_agent_settings(self):
        """Accept both current PAPERMATE_AGENT_* and remote LLM names."""
        if self.agent_enabled is not None:
            # The legacy switch controls every Agent when explicitly provided.
            self.parse_agent_enabled = self.agent_enabled
            self.qa_agent_enabled = self.agent_enabled
            self.search_agent_enabled = self.agent_enabled
            self.graph_agent_enabled = self.agent_enabled
            self.assist_agent_enabled = self.agent_enabled
        if not self.llm_api_key.strip() and self.agent_api_key:
            self.llm_api_key = self.agent_api_key.strip()
        if not self.llm_api_key.strip() and self.deepseek_api_key.strip():
            self.llm_api_key = self.deepseek_api_key.strip()
        if self.deepseek_api_base.strip():
            self.llm_api_base = self.deepseek_api_base.strip()
        elif self.agent_base_url.strip() and self.agent_base_url != "https://api.openai.com/v1":
            self.llm_api_base = self.agent_base_url.rstrip("/")
        if self.deepseek_model.strip():
            self.llm_model = self.deepseek_model.strip()
        elif self.agent_model.strip():
            self.llm_model = self.agent_model.strip()
        if self.agent_timeout_s != 30.0:
            self.qa_agent_timeout_s = self.agent_timeout_s
        if self.environment == "test":
            self.crawl_enabled = False
        return self

    @property
    def parse_agent_ready(self) -> bool:
        return bool(self.parse_agent_enabled and self.llm_api_key.strip() and self.llm_model.strip())

    @property
    def qa_agent_ready(self) -> bool:
        return bool(self.qa_agent_enabled and self.llm_api_key.strip() and self.llm_model.strip())

    @property
    def search_agent_ready(self) -> bool:
        return bool(self.search_agent_enabled and self.llm_api_key.strip())

    @property
    def graph_agent_ready(self) -> bool:
        return bool(self.graph_agent_enabled and self.llm_api_key.strip() and self.llm_model.strip())

    @property
    def assist_agent_ready(self) -> bool:
        return bool(self.assist_agent_enabled and self.llm_api_key.strip() and self.llm_model.strip())

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
