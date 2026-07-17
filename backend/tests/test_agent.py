from app.core.config import Settings
from app.service.agent import AgentClient


def test_agent_is_disabled_without_explicit_configuration() -> None:
    client = AgentClient(Settings(environment="test", agent_enabled=False, agent_model="demo"))

    assert client.enabled is False
