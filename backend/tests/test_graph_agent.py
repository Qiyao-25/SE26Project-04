from app.agents.graph_agent import GraphAgent


def test_graph_agent_builds_explainable_entities_and_relations() -> None:
    graph = GraphAgent(None).run(
        paper_id=1,
        title="Attention Model",
        abstract="An attention model is evaluated on GLUE benchmark tasks.",
        arxiv_id="paper-1",
        primary_category="cs.CL",
        published_at="2020-01-01T00:00:00+00:00",
        concepts=[{"name": "Attention", "description": "attention representation"}],
        methods=[{"title": "Attention encoder", "description": "implements attention"}],
        experiments=[{"title": "GLUE benchmark", "description": "evaluation on GLUE"}],
        limitations=["needs more data"],
        related_papers=[
            {"paper_id": 2, "title": "Earlier Attention Work", "abstract": "attention encoder", "primary_category": "cs.CL", "published_at": "2019-01-01T00:00:00+00:00"},
            {"paper_id": 3, "title": "Later Attention Work", "abstract": "attention encoder", "primary_category": "cs.CL", "published_at": "2021-01-01T00:00:00+00:00"},
        ],
    )

    node_types = {node["type"] for node in graph.nodes}
    edge_types = {edge["type"] for edge in graph.edges}
    node_ids = [node["id"] for node in graph.nodes]

    assert len(node_ids) == len(set(node_ids))
    assert {"paper", "concept", "method", "dataset", "task"} <= node_types
    assert {"introduces", "uses", "evaluates_on", "precedes", "follows"} <= edge_types
    assert any(item["role"] == "predecessor" for item in graph.lineage)
    assert any(item["role"] == "successor" for item in graph.lineage)
    assert "并非真实引用关系" in graph.narrative
