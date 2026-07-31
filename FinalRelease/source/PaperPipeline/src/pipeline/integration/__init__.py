"""Integration adapters — swap local fallback for member C APIs when ready."""

from .chunks_client import ChunksClient, TextChunkRef
from .backend_client import BackendClient
from .config import IntegrationConfig
from .contracts import (
    citation_to_ui,
    paper_meta_to_backend,
    paragraphs_to_text_chunks,
    pipeline_status_to_orm,
    qa_result_to_ui,
    wiki_to_backend_structured,
    wiki_to_backend_structured_rows,
    wiki_to_ui_summary,
)

__all__ = [
    "ChunksClient",
    "BackendClient",
    "TextChunkRef",
    "IntegrationConfig",
    "paper_meta_to_backend",
    "pipeline_status_to_orm",
    "wiki_to_backend_structured",
    "wiki_to_backend_structured_rows",
    "wiki_to_ui_summary",
    "citation_to_ui",
    "qa_result_to_ui",
    "paragraphs_to_text_chunks",
]
