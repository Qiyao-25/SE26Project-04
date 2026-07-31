"""Optional model-backed agents for parsing and structured extraction."""

from .client import AgentCallError, AgentConfig, ChatAgent
from .structured_parser import build_structured_with_agent

__all__ = ["AgentCallError", "AgentConfig", "ChatAgent", "build_structured_with_agent"]
