from fastapi.testclient import TestClient

from app.main import app
from app.services.evaluation import agent_route_eval_service, retrieval_eval_service


def test_retrieval_evaluation_endpoint_returns_report(monkeypatch):
    client = TestClient(app)

    def fake_eval(dataset_name: str, top_k: int):
        assert dataset_name == "rag_overview_retrieval_eval.json"
        assert top_k == 3
        return {
            "top_k": 3,
            "summary": {
                "total_cases": 2,
                "hit_rate_at_k": 1.0,
                "mean_reciprocal_rank": 0.75,
            },
            "cases": [
                {
                    "case_id": "case_1",
                    "filename": "rag_overview.md",
                    "question": "What is RAG?",
                    "expected_chunk_ids": ["rag_overview.md::chunk_0"],
                    "retrieved_chunk_ids": ["rag_overview.md::chunk_0"],
                    "hit_at_k": True,
                    "reciprocal_rank": 1.0,
                }
            ],
        }

    monkeypatch.setattr(
        retrieval_eval_service,
        "evaluate_named_retrieval_dataset",
        fake_eval,
    )

    response = client.post(
        "/api/evaluation/retrieval",
        json={
            "dataset_name": "rag_overview_retrieval_eval.json",
            "top_k": 3,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_name"] == "rag_overview_retrieval_eval.json"
    assert payload["report"]["summary"]["hit_rate_at_k"] == 1.0


def test_retrieval_evaluation_endpoint_returns_404_for_missing_dataset(monkeypatch):
    client = TestClient(app)

    def fake_eval(dataset_name: str, top_k: int):
        raise FileNotFoundError(dataset_name)

    monkeypatch.setattr(
        retrieval_eval_service,
        "evaluate_named_retrieval_dataset",
        fake_eval,
    )

    response = client.post(
        "/api/evaluation/retrieval",
        json={
            "dataset_name": "missing.json",
            "top_k": 3,
        },
    )

    assert response.status_code == 404


def test_retrieval_evaluation_dataset_list_endpoint_returns_datasets(monkeypatch):
    client = TestClient(app)

    def fake_list():
        return [
            {
                "dataset_name": "rag_overview_retrieval_eval.json",
                "case_count": 6,
                "filenames": ["rag_overview.md"],
            },
            {
                "dataset_name": "agent_workflow_retrieval_eval.json",
                "case_count": 8,
                "filenames": ["agent_workflow.md"],
            },
        ]

    monkeypatch.setattr(
        retrieval_eval_service,
        "list_retrieval_datasets",
        fake_list,
    )

    response = client.get("/api/evaluation/retrieval/datasets")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["datasets"]) == 2
    assert payload["datasets"][0]["dataset_name"] == "rag_overview_retrieval_eval.json"


def test_agent_route_evaluation_endpoint_returns_report(monkeypatch):
    client = TestClient(app)

    def fake_eval(dataset_name: str):
        assert dataset_name == "agent_route_eval.json"
        return {
            "summary": {
                "total_cases": 2,
                "route_accuracy": 1.0,
            },
            "cases": [
                {
                    "case_id": "case_1",
                    "question": "What is RAG?",
                    "filename": "rag_overview.md",
                    "expected_route_type": "knowledge_retrieval",
                    "actual_route_type": "knowledge_retrieval",
                    "route_reason": "matched",
                    "matched": True,
                }
            ],
        }

    monkeypatch.setattr(
        agent_route_eval_service,
        "evaluate_named_agent_route_dataset",
        fake_eval,
    )

    response = client.post(
        "/api/evaluation/agent-route",
        json={
            "dataset_name": "agent_route_eval.json",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_name"] == "agent_route_eval.json"
    assert payload["report"]["summary"]["route_accuracy"] == 1.0


def test_agent_route_evaluation_dataset_list_endpoint_returns_datasets(monkeypatch):
    client = TestClient(app)

    def fake_list():
        return [
            {
                "dataset_name": "agent_route_eval.json",
                "case_count": 6,
            }
        ]

    monkeypatch.setattr(
        agent_route_eval_service,
        "list_agent_route_datasets",
        fake_list,
    )

    response = client.get("/api/evaluation/agent-route/datasets")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["datasets"]) == 1
    assert payload["datasets"][0]["dataset_name"] == "agent_route_eval.json"
