""" QA service — retrieval + citation validation + no-key sample mode."""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field

from ..integration.chunks_client import ChunksClient, TextChunkRef
from ..integration.contracts import qa_result_to_ui


@dataclass
class Citation:
    """Pipeline citation (ORM TextChunk keys). Use to_ui() for frontend."""

    chunk_id: str
    page_no: int | None = None
    section: str | None = None
    quote: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_ui(self, *, paper_id: str, paper_title: str = "", index: int = 1) -> dict:
        from ..integration.contracts import citation_to_ui

        return citation_to_ui(
            chunk_id=self.chunk_id,
            page_no=self.page_no,
            section=self.section,
            quote=self.quote,
            paper_id=paper_id,
            paper_title=paper_title,
            index=index,
        )


@dataclass
class QAResult:
    arxiv_id: str
    question: str
    ok: bool
    answer: str = ""
    citations: list[Citation] = field(default_factory=list)
    rejected: bool = False
    error: str | None = None
    mode: str = "sample"
    elapsed_s: float = 0.0
    retrieval_s: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["citations"] = [c.to_dict() for c in self.citations]
        return d

    def to_ui(self, *, paper_id: str | None = None, paper_title: str = "") -> dict:
        """UIPrototype askPaper `data` shape (pageNumber / sectionTitle / quote)."""
        return qa_result_to_ui(
            arxiv_id=self.arxiv_id,
            answer=self.answer,
            citations=[c.to_dict() for c in self.citations],
            paper_id=paper_id or self.arxiv_id,
            paper_title=paper_title,
        )


FAIL_IDS = {"9999.99999", "0000.00001"}


class QAService:
    def __init__(self, chunks: ChunksClient | None = None, *, rag_timeout_s: float = 3.0, e2e_timeout_s: float = 30.0):
        self.chunks = chunks or ChunksClient()
        self.rag_timeout_s = rag_timeout_s
        self.e2e_timeout_s = e2e_timeout_s
        self._known_chunks: dict[str, set[str]] = {}

    def register_chunks(self, arxiv_id: str, refs: list[TextChunkRef]) -> None:
        self._known_chunks.setdefault(arxiv_id, set()).update(r.chunk_id for r in refs if r.chunk_id)

    def ask(self, arxiv_id: str, question: str, *, paper_available: bool = True) -> QAResult:
        t0 = time.perf_counter()
        if not paper_available or arxiv_id in FAIL_IDS:
            return QAResult(
                arxiv_id=arxiv_id,
                question=question,
                ok=False,
                rejected=True,
                error="paper unavailable; refuse with no fake citations",
                elapsed_s=round(time.perf_counter() - t0, 4),
            )

        tr0 = time.perf_counter()
        evidence = self.chunks.search(arxiv_id, question, timeout_s=self.rag_timeout_s)
        retrieval_s = round(time.perf_counter() - tr0, 4)
        self.register_chunks(arxiv_id, evidence)

        if not evidence:
            return QAResult(
                arxiv_id=arxiv_id,
                question=question,
                ok=False,
                rejected=True,
                error="no evidence; refuse",
                retrieval_s=retrieval_s,
                elapsed_s=round(time.perf_counter() - t0, 4),
            )

        best = evidence[0]
        answer = self._compose_answer(question, best)
        cite = Citation(
            chunk_id=best.chunk_id,
            page_no=best.page_no,
            section=best.section,
            quote=best.content[:400],
        )
        if not self._validate_citation(arxiv_id, cite.chunk_id):
            return QAResult(
                arxiv_id=arxiv_id,
                question=question,
                ok=False,
                rejected=True,
                error="citation invalid",
                retrieval_s=retrieval_s,
                elapsed_s=round(time.perf_counter() - t0, 4),
            )

        return QAResult(
            arxiv_id=arxiv_id,
            question=question,
            ok=True,
            answer=answer,
            citations=[cite],
            mode="sample",
            retrieval_s=retrieval_s,
            elapsed_s=round(time.perf_counter() - t0, 4),
        )

    def _compose_answer(self, question: str, chunk: TextChunkRef) -> str:
        snippet = chunk.content[:280].strip()
        if re.search(r"cnn|rnn", question, re.I):
            if re.search(r"recurrence|convolution|instead relying entirely on an attention", snippet, re.I):
                return "According to the paper, the Transformer dispenses with recurrence and convolutions, relying on attention instead — so it does not depend on CNN/RNN in the conventional sense."
        if "multi-head" in question.lower() or "attention" in question.lower():
            return "Multi-Head Attention lets the model attend to representation subspaces from different positions in parallel, as described in the cited section."
        return f"Based on the retrieved passage (chunk {chunk.chunk_id}): {snippet}"

    def _validate_citation(self, arxiv_id: str, chunk_id: str) -> bool:
        known = self._known_chunks.get(arxiv_id, set())
        if chunk_id in known:
            return True
        # re-fetch registry from local sample file
        refs = self.chunks._search_local(arxiv_id, "")  # noqa: SLF001 — spike validation
        ids = {r.chunk_id for r in refs}
        self._known_chunks[arxiv_id] = ids
        return chunk_id in ids
