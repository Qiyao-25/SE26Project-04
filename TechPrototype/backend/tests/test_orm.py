from sqlalchemy import create_engine, inspect

from app.model import Base


def test_h005_orm_registers_core_tables() -> None:
    expected = {"papers", "authors", "paper_authors", "paper_contents", "parse_tasks", "structured_results", "text_chunks", "user_actions", "user_profiles", "users"}
    assert expected.issubset(Base.metadata.tables)


def test_orm_can_create_and_inspect_tables() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    assert set(inspect(engine).get_table_names()) == {"authors", "paper_authors", "paper_contents", "papers", "parse_tasks", "structured_results", "text_chunks", "user_actions", "user_profiles", "users"}
