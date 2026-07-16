"""Integration adapters — swap local fallback for member C/A/E APIs when ready.

Env:
- PAPERMATE_API_BASE          → C backend (papers/parse/wiki/chunks)
- PAPERMATE_QA_MODE=sample    → no LLM (default)
- PAPERMATE_QA_MODE=remote    → future remote QA/LLM
"""

from .chunks_client import ChunksClient, TextChunkRef
from .config import IntegrationConfig
from .contracts import (
    citation_to_ui,
    paper_meta_to_backend,
    pipeline_status_to_orm,
    qa_result_to_ui,
    wiki_to_backend_structured,
    wiki_to_ui_summary,
)

__all__ = [
    "ChunksClient",
    "TextChunkRef",
    "IntegrationConfig",
    "paper_meta_to_backend",
    "pipeline_status_to_orm",
    "wiki_to_backend_structured",
    "wiki_to_ui_summary",
    "citation_to_ui",
    "qa_result_to_ui",
]
