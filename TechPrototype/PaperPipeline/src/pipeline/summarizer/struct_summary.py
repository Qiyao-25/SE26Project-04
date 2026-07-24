""" · Extractive summary / concept / methods from parsed paragraphs."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from ..parser.pdf_parse import Paragraph
from ..validation import ContentValidationAgent

_KW = re.compile(
    r"\b(model|attention|transformer|method|approach|propose|learning|network|"
    r"retrieve|generation|parameter|training|architecture)\b",
    re.I,
)


@dataclass
class StructuredWiki:
    arxiv_id: str
    summary: str
    concept: str
    methods: str
    experiments: str
    limitations: list[str]
    ok: bool
    source_para_ids: list[str]
    validation_flags: list[str]

    def required_ok(self) -> bool:
        return bool(self.summary and self.concept and self.methods and self.experiments)

    def to_dict(self) -> dict:
        return asdict(self)


def _score_sent(s: str) -> int:
    return len(_KW.findall(s))


def _pick(texts: list[str], limit: int, min_len: int = 40) -> list[str]:
    scored = []
    for t in texts:
        for s in re.split(r"(?<=[.!?])\s+", t):
            s = s.strip()
            if min_len <= len(s) <= 400:
                scored.append((_score_sent(s), s))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    seen = set()
    for _, s in scored:
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
        if len(out) >= limit:
            break
    return out


def build_structured(
    arxiv_id: str,
    paragraphs: list[Paragraph],
    *,
    title: str = "",
    abstract_hint: str = "",
) -> StructuredWiki:
    if not paragraphs:
        return StructuredWiki(arxiv_id, "", "", "", "", [], False, [], ["missing_paragraphs"])

    by_section: dict[str, list[Paragraph]] = {}
    for p in paragraphs:
        by_section.setdefault(p.section, []).append(p)

    intro = by_section.get("introduction") or by_section.get("abstract") or paragraphs[:8]
    methods_paras = []
    for key in ("method", "methods", "approach", "architecture"):
        methods_paras.extend(by_section.get(key, []))
    if not methods_paras:
        methods_paras = paragraphs[len(paragraphs) // 4 : len(paragraphs) // 2]

    experiment_paras = []
    for key in ("experiment", "experiments", "results", "evaluation"):
        experiment_paras.extend(by_section.get(key, []))
    if not experiment_paras:
        experiment_paras = paragraphs[len(paragraphs) // 2 : len(paragraphs) * 3 // 4]

    limitation_paras = []
    for key in ("discussion", "conclusion", "limitations"):
        limitation_paras.extend(by_section.get(key, []))

    intro_texts = [p.text for p in intro]
    method_texts = [p.text for p in methods_paras]
    experiment_texts = [p.text for p in experiment_paras]
    limitation_texts = [p.text for p in limitation_paras]
    all_texts = [p.text for p in paragraphs[:40]]

    summary_bits = []
    if abstract_hint:
        summary_bits.append(abstract_hint[:500])
    summary_bits.extend(_pick(intro_texts or all_texts, 2))
    if title:
        summary_bits.insert(0, f"Paper: {title}.")
    summary = " ".join(summary_bits)[:1200]

    concept = " ".join(_pick(intro_texts or all_texts, 4))[:900]
    methods = " ".join(_pick(method_texts or all_texts, 3))[:900]
    experiments = " ".join(_pick(experiment_texts or all_texts, 3))[:900]
    if not experiments:
        experiments = "实验与结果章节未从解析文本中识别，需人工校验。"
    limitations = _pick(limitation_texts, 3)

    ids = [p.para_id for p in (intro[:2] + methods_paras[:2] + experiment_paras[:2])]
    validation_flags = ContentValidationAgent().validate(
        summary=summary,
        concept=concept,
        methods=methods,
        experiments=experiments,
        source_para_ids=ids,
        paragraphs=paragraphs,
    ).flags

    result = StructuredWiki(
        arxiv_id=arxiv_id,
        summary=summary.strip(),
        concept=concept.strip(),
        methods=methods.strip(),
        experiments=experiments.strip(),
        limitations=limitations,
        ok=bool(summary and concept and methods and experiments),
        source_para_ids=ids,
        validation_flags=validation_flags,
    )
    return result
