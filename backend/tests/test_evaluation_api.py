from fastapi.testclient import TestClient

from app.main import app
from app.services.evaluation import retrieval_eval_service


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
