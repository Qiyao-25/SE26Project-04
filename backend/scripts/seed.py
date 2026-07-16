from datetime import datetime

from app.core.config import get_settings
from app.core.database import create_engine_for
from app.model import Base
from app.schema.papers import AuthorInput, PaperUpsert
from app.service.papers import batch_upsert_papers


SEED = [
    ("1706.03762", "Attention Is All You Need", ["Vaswani", "Shazeer", "Parmar"], "提出 Transformer 架构，完全基于注意力机制，在机器翻译任务达到 SOTA。", "cs.CL", "2017-06-12"),
    ("1810.04805", "BERT: Pre-training of Deep Bidirectional Transformers", ["Devlin", "Chang", "Lee", "Toutanova"], "双向预训练语言表示模型，奠定预训练-微调范式。", "cs.CL", "2018-10-11"),
    ("2005.14165", "GPT-3: Language Models are Few-Shot Learners", ["Brown", "Mann", "Ryder"], "规模化语言模型展示少样本学习能力与涌现特性。", "cs.LG", "2020-05-28"),
    ("2106.09685", "LoRA: Low-Rank Adaptation of Large Language Models", ["Hu", "Shen", "Wallis"], "低秩适配实现参数高效微调，适用于大模型。", "cs.LG", "2021-06-17"),
    ("2005.11401", "Retrieval-Augmented Generation for Knowledge-Intensive NLP", ["Lewis", "Perez", "Piktus"], "检索增强生成架构，结合外部知识库提升问答质量。", "cs.CL", "2020-05-22"),
    ("2607.01001", "Vision-Language Models for Scientific Document Understanding", ["Li", "Zhang", "Wang"], "多模态模型用于科学文档解析与理解。", "cs.CV", "2026-07-07"),
]


def main() -> None:
    settings = get_settings()
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import Session

    payloads = [
        PaperUpsert(
            arxiv_id=arxiv_id,
            title=title,
            authors=[AuthorInput(name=author) for author in authors],
            abstract=abstract,
            published_at=datetime.fromisoformat(published_at),
            primary_category=category,
            pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
            source_url=f"https://arxiv.org/abs/{arxiv_id}",
        )
        for arxiv_id, title, authors, abstract, category, published_at in SEED
    ]
    with Session(engine) as session:
        result = batch_upsert_papers(session, payloads)
    print(f"seeded={len(result.items)} created={result.created} updated={result.updated}")


if __name__ == "__main__":
    main()
