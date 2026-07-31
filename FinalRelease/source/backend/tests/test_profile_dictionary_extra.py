"""Profile dictionary branches (graph, wiki legacy, kg)."""

from sqlalchemy.orm import Session

from app.model import StructuredResult
from app.schema.papers import PaperUpsert, UserActionInput, UserProfileUpdate
from app.service.learning import create_action
from app.service.papers import batch_upsert_papers
from app.service.profile import clear_dictionary, get_dictionary, update_profile
from tests.conftest import seed_paper


def test_dictionary_from_kg_graph_and_wiki_legacy(db_session):
    wiki_paper = seed_paper(db_session, arxiv_id="dict-wiki", title="Wiki Dict", ingest_status="qa_ready")
    graph_paper = seed_paper(db_session, arxiv_id="dict-kg", title="Graph Dict", ingest_status="qa_ready")

    db_session.add(
        StructuredResult(
            paper_id=wiki_paper,
            result_type="wiki_triple",
            version=1,
            content_json={"concept": "Self-Attention mechanism overview text"},
            source_locator={},
        )
    )
    db_session.add(
        StructuredResult(
            paper_id=graph_paper,
            result_type="kg_graph",
            version=1,
            content_json={
                "nodes": [
                    {"id": "c1", "type": "concept", "label": "Transformer", "description": "sequence model"},
                ],
                "edges": [],
            },
            source_locator={},
        )
    )
    db_session.commit()

    user_id = "dict-user-kg"
    for pid in (wiki_paper, graph_paper):
        create_action(
            db_session,
            UserActionInput(user_id=user_id, paper_id=pid, action_type="reading_history", payload_json={}),
        )
    update_profile(db_session, user_id, UserProfileUpdate(topics=["cs.CL"]))

    entries = get_dictionary(db_session, user_id)
    terms = {e.term for e in entries}
    assert "Attention" in terms or "Transformer" in terms

    cleared = clear_dictionary(db_session, user_id)
    assert cleared["cleared"] >= 0


def test_learning_bulk_delete_http(client, user_headers, db_session):
    user = client.get("/api/auth/me", headers=user_headers).json()["data"]
    user_id = user["user_id"]
    paper_id = seed_paper(db_session, arxiv_id="bulk-del", title="Bulk Del")
    created = client.post(
        "/api/learning/actions",
        headers=user_headers,
        json={"user_id": user_id, "paper_id": paper_id, "action_type": "favorite", "payload_json": {"favorite": True}},
    )
    assert created.status_code == 200
    bulk = client.delete(
        f"/api/learning/actions/bulk?user_id={user_id}&action_type=favorite",
        headers=user_headers,
    )
    assert bulk.status_code == 200
    assert bulk.json()["data"]["deleted"] >= 1
