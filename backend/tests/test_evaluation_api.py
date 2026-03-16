from fastapi.testclient import TestClient

from app.main import app
from app.services.evaluation import (
    agent_route_eval_service,
    tool_execution_eval_service,
    agent_workflow_eval_service,
    overview_service,
    retrieval_eval_service,
)


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


def test_agent_workflow_evaluation_endpoint_returns_report(monkeypatch):
    client = TestClient(app)

    def fake_eval(dataset_name: str):
        assert dataset_name == "agent_workflow_eval.json"
        return {
            "summary": {
                "total_cases": 3,
                "workflow_accuracy": 1.0,
            },
            "cases": [
                {
                    "case_id": "case_1",
                    "question": "What is RAG?",
                    "filename": "rag_overview.md",
                    "expected_route_type": "knowledge_retrieval",
                    "actual_route_type": "knowledge_retrieval",
                    "expected_workflow_status": "completed",
                    "actual_workflow_status": "completed",
                    "route_reason": "matched",
                    "matched": True,
                }
            ],
        }

    monkeypatch.setattr(
        agent_workflow_eval_service,
        "evaluate_named_agent_workflow_dataset",
        fake_eval,
    )

    response = client.post(
        "/api/evaluation/agent-workflow",
        json={
            "dataset_name": "agent_workflow_eval.json",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_name"] == "agent_workflow_eval.json"
    assert payload["report"]["summary"]["workflow_accuracy"] == 1.0


def test_agent_workflow_evaluation_dataset_list_endpoint_returns_datasets(monkeypatch):
    client = TestClient(app)

    def fake_list():
        return [
            {
                "dataset_name": "agent_workflow_eval.json",
                "case_count": 6,
            }
        ]

    monkeypatch.setattr(
        agent_workflow_eval_service,
        "list_agent_workflow_datasets",
        fake_list,
    )

    response = client.get("/api/evaluation/agent-workflow/datasets")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["datasets"]) == 1
    assert payload["datasets"][0]["dataset_name"] == "agent_workflow_eval.json"


def test_tool_execution_evaluation_endpoint_returns_report(monkeypatch):
    client = TestClient(app)

    def fake_eval(dataset_name: str):
        assert dataset_name == "agent_tool_execution_eval.json"
        return {
            "summary": {
                "total_cases": 2,
                "tool_accuracy": 1.0,
            },
            "cases": [
                {
                    "case_id": "case_1",
                    "question": "Search docs for RAG",
                    "expected_tool_name": "document_search",
                    "actual_tool_name": "document_search",
                    "expected_action": "query",
                    "actual_action": "query",
                    "expected_execution_status": "completed",
                    "actual_execution_status": "completed",
                    "matched": True,
                    "argument_matches": {},
                    "output_matches": {},
                    "output_key_matches": {
                        "query": True,
                    },
                }
            ],
        }

    monkeypatch.setattr(
        tool_execution_eval_service,
        "evaluate_named_tool_execution_dataset",
        fake_eval,
    )

    response = client.post(
        "/api/evaluation/tool-execution",
        json={
            "dataset_name": "agent_tool_execution_eval.json",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_name"] == "agent_tool_execution_eval.json"
    assert payload["report"]["summary"]["tool_accuracy"] == 1.0


def test_tool_execution_evaluation_dataset_list_endpoint_returns_datasets(monkeypatch):
    client = TestClient(app)

    def fake_list():
        return [
            {
                "dataset_name": "agent_tool_execution_eval.json",
                "case_count": 4,
            }
        ]

    monkeypatch.setattr(
        tool_execution_eval_service,
        "list_tool_execution_datasets",
        fake_list,
    )

    response = client.get("/api/evaluation/tool-execution/datasets")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["datasets"]) == 1
    assert payload["datasets"][0]["dataset_name"] == "agent_tool_execution_eval.json"


def test_evaluation_overview_endpoint_returns_aggregated_metrics(monkeypatch):
    client = TestClient(app)

    def fake_overview(top_k: int = 3, refresh: bool = False):
        assert top_k == 3
        assert refresh is False
        return {
            "generated_at": "2026-03-17T00:00:00+00:00",
            "cache_status": "cached",
            "retrieval": {
                "dataset_count": 2,
                "total_cases": 12,
                "mean_hit_rate_at_k": 0.875,
                "mean_reciprocal_rank": 0.71,
                "best_dataset_name": "rag_overview_retrieval_eval.json",
                "best_hit_rate_at_k": 1.0,
            },
            "workflow": {
                "total_run_count": 20,
                "completed_run_count": 12,
                "clarification_required_run_count": 3,
                "failed_run_count": 5,
                "completion_rate": 0.6,
                "clarification_rate": 0.15,
                "failed_rate": 0.25,
            },
            "recovery": {
                "recovered_run_count": 6,
                "recovered_completed_run_count": 5,
                "recovery_success_rate": 0.8333333333,
                "average_recovery_depth": 1.33,
                "resume_from_failed_step_count": 3,
                "manual_retrigger_count": 2,
                "clarification_recovery_count": 1,
            },
        }

    monkeypatch.setattr(overview_service, "get_evaluation_overview", fake_overview)

    response = client.get("/api/evaluation/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval"]["dataset_count"] == 2
    assert payload["workflow"]["completion_rate"] == 0.6
    assert payload["recovery"]["resume_from_failed_step_count"] == 3
    assert payload["cache_status"] == "cached"
