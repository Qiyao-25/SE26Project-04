from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base
from app.schema.papers import PaperUpsert
from app.service.papers import batch_upsert_papers


def test_upsert_dedupes_by_normalized_title(tmp_path) -> None:
    settings = Settings(environment="test", database_url=f"sqlite:///{tmp_path / 'dedupe.db'}")
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        first = batch_upsert_papers(
            session,
            [PaperUpsert(arxiv_id="1706.03762", title="Attention Is All You Need", primary_category="cs.CL")],
        )
        second = batch_upsert_papers(
            session,
            [PaperUpsert(arxiv_id="9999.00001", title="Attention Is All You Need!", primary_category="cs.LG")],
        )
        assert first.created == 1
        assert second.created == 0
        assert second.updated == 1
        assert first.items[0].paper_id == second.items[0].paper_id
