"""Import PaperPipeline/data/seed.json into the configured database."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import create_engine_for
from app.schema.papers import AuthorInput, PaperUpsert
from app.service.papers import batch_upsert_papers


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    # Python 3.10 fromisoformat does not accept trailing Z
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    return datetime.fromisoformat(normalized)


def load_payload(seed_path: Path) -> list[PaperUpsert]:
    document = json.loads(seed_path.read_text(encoding="utf-8"))
    rows = document.get("papers", document)
    if not isinstance(rows, list):
        raise ValueError("seed 文件必须包含 papers 数组")
    payloads = []
    for row in rows:
        categories = row.get("categories") or []
        authors = row.get("authors") or []
        payloads.append(
            PaperUpsert(
                arxiv_id=str(row.get("arxiv_id", "")).removesuffix(".pdf"),
                title=row.get("title", ""),
                authors=[AuthorInput(name=(author.get("name") or author.get("display_name")) if isinstance(author, dict) else author) for author in authors],
                abstract=row.get("abstract"),
                published_at=_parse_datetime(row.get("published_at") or row.get("published")),
                primary_category=categories[0] if categories else row.get("primary_category"),
                pdf_url=row.get("pdf_url"),
                source_url=row.get("source_url") or row.get("abs_url"),
                ingest_status=row.get("ingest_status", "metadata_only"),
            )
        )
    return payloads


def main() -> None:
    parser = argparse.ArgumentParser(description="Import PaperPipeline seed data")
    parser.add_argument("--seed", type=Path, default=Path("../PaperPipeline/data/seed.json"))
    args = parser.parse_args()
    payloads = load_payload(args.seed)
    with Session(create_engine_for(get_settings())) as session:
        result = batch_upsert_papers(session, payloads)
    print(f"imported={len(result.items)} created={result.created} updated={result.updated}")


if __name__ == "__main__":
    main()
