from fastapi.testclient import TestClient

from app.main import app
from app.services.evaluation import (
    agent_route_eval_service,
    export_bundle_service,
    tool_execution_eval_service,
    agent_workflow_eval_service,
    metrics_summary_service,
    overview_service,
    report_store_service,
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
    monkeypatch.setattr(
        report_store_service,
        "persist_retrieval_report",
        lambda dataset_name, top_k, report: {
            "dataset_name": dataset_name,
            "top_k": top_k,
            "saved_at": "2026-03-17T01:00:00+00:00",
            "report_source": "fresh",
            "report": report,
        },
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
    assert payload["report_source"] == "fresh"
    assert payload["saved_at"] == "2026-03-17T01:00:00+00:00"


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
    monkeypatch.setattr(
        report_store_service,
        "persist_agent_route_report",
        lambda dataset_name, report: {
            "dataset_name": dataset_name,
            "saved_at": "2026-03-17T01:05:00+00:00",
            "report_source": "fresh",
            "report": report,
        },
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
    assert payload["report_source"] == "fresh"


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
    monkeypatch.setattr(
        report_store_service,
        "persist_agent_workflow_report",
        lambda dataset_name, report: {
            "dataset_name": dataset_name,
            "saved_at": "2026-03-17T01:10:00+00:00",
            "report_source": "fresh",
            "report": report,
        },
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
    assert payload["report_source"] == "fresh"


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
    monkeypatch.setattr(
        report_store_service,
        "persist_tool_execution_report",
        lambda dataset_name, report: {
            "dataset_name": dataset_name,
            "saved_at": "2026-03-17T01:15:00+00:00",
            "report_source": "fresh",
            "report": report,
        },
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
    assert payload["report_source"] == "fresh"


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


def test_evaluation_metrics_summary_endpoint_returns_curated_metrics(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        metrics_summary_service,
        "get_metrics_summary",
        lambda refresh=False: {
            "generated_at": "2026-03-17T03:00:00+00:00",
            "cache_status": "cached",
            "highlights": [
                {
                    "label": "Workflow Completion",
                    "value": "63.7%",
                    "detail": "107/168 runs completed.",
                }
            ],
            "sections": [
                {
                    "title": "Showcase Retrieval Benchmark",
                    "dataset_name": "agent_workflow_retrieval_eval.json",
                    "metric_name": "hit_rate_at_k",
                    "metric_value": 1.0,
                    "formatted_value": "1.000",
                    "detail": "MRR 0.917 at top-3.",
                }
            ],
        },
    )

    response = client.get("/api/evaluation/metrics-summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["cache_status"] == "cached"
    assert payload["highlights"][0]["label"] == "Workflow Completion"
    assert payload["sections"][0]["dataset_name"] == "agent_workflow_retrieval_eval.json"


def test_evaluation_export_bundle_endpoint_returns_showcase_payload(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        export_bundle_service,
        "get_evaluation_export_bundle",
        lambda refresh=False: {
            "generated_at": "2026-03-17T04:00:00+00:00",
            "overview": {
                "generated_at": "2026-03-17T03:55:00+00:00",
                "cache_status": "cached",
                "retrieval": {
                    "dataset_count": 4,
                    "total_cases": 28,
                    "mean_hit_rate_at_k": 0.76,
                    "mean_reciprocal_rank": 0.533,
                    "best_dataset_name": "rag_overview_retrieval_eval.json",
                    "best_hit_rate_at_k": 1.0,
                },
                "workflow": {
                    "total_run_count": 168,
                    "completed_run_count": 107,
                    "clarification_required_run_count": 39,
                    "failed_run_count": 22,
                    "completion_rate": 0.637,
                    "clarification_rate": 0.232,
                    "failed_rate": 0.131,
                },
                "recovery": {
                    "recovered_run_count": 19,
                    "recovered_completed_run_count": 19,
                    "recovery_success_rate": 1.0,
                    "average_recovery_depth": 1.0,
                    "resume_from_failed_step_count": 4,
                    "manual_retrigger_count": 1,
                    "clarification_recovery_count": 1,
                },
            },
            "metrics_summary": {
                "generated_at": "2026-03-17T03:55:00+00:00",
                "cache_status": "cached",
                "highlights": [
                    {"label": "Workflow Completion", "value": "63.7%", "detail": "107/168 runs completed."}
                ],
                "sections": [
                    {
                        "title": "Showcase Retrieval",
                        "dataset_name": "agent_workflow_retrieval_eval.json",
                        "metric_name": "hit_rate_at_k",
                        "metric_value": 1.0,
                        "formatted_value": "1.000",
                        "detail": "MRR 0.917 at top-3.",
                    }
                ],
            },
            "reports": {
                "retrieval": {
                    "dataset_name": "agent_workflow_retrieval_eval.json",
                    "top_k": 3,
                    "latest_report": {"dataset_name": "agent_workflow_retrieval_eval.json"},
                    "history": [],
                },
                "agent_route": {
                    "dataset_name": "agent_route_eval.json",
                    "top_k": None,
                    "latest_report": {"dataset_name": "agent_route_eval.json"},
                    "history": [],
                },
                "agent_workflow": {
                    "dataset_name": "agent_workflow_eval.json",
                    "top_k": None,
                    "latest_report": {"dataset_name": "agent_workflow_eval.json"},
                    "history": [],
                },
                "tool_execution": {
                    "dataset_name": "agent_tool_execution_eval.json",
                    "top_k": None,
                    "latest_report": {"dataset_name": "agent_tool_execution_eval.json"},
                    "history": [],
                },
            },
        },
    )

    response = client.get("/api/evaluation/export-bundle")

    assert response.status_code == 200
    payload = response.json()
    assert payload["metrics_summary"]["highlights"][0]["label"] == "Workflow Completion"
    assert payload["reports"]["tool_execution"]["dataset_name"] == "agent_tool_execution_eval.json"


def test_latest_retrieval_evaluation_endpoint_returns_saved_report(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        report_store_service,
        "load_latest_retrieval_report",
        lambda dataset_name, top_k: {
            "dataset_name": dataset_name,
            "saved_at": "2026-03-17T02:00:00+00:00",
            "report_source": "saved",
            "report": {
                "top_k": top_k,
                "summary": {
                    "total_cases": 2,
                    "hit_rate_at_k": 0.5,
                    "mean_reciprocal_rank": 0.5,
                },
                "cases": [],
            },
        },
    )

    response = client.get(
        "/api/evaluation/retrieval/latest?dataset_name=rag_overview_retrieval_eval.json&top_k=3",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["report_source"] == "saved"
    assert payload["saved_at"] == "2026-03-17T02:00:00+00:00"


def test_retrieval_evaluation_history_endpoint_returns_entries(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        report_store_service,
        "list_retrieval_report_history",
        lambda dataset_name, top_k, limit=5: [
            {
                "dataset_name": dataset_name,
                "saved_at": "2026-03-17T02:00:00+00:00",
                "report_source": "saved",
                "top_k": top_k,
                "primary_metric_name": "hit_rate_at_k",
                "primary_metric_value": 0.75,
                "case_count": 8,
            }
        ],
    )

    response = client.get(
        "/api/evaluation/retrieval/history?dataset_name=rag_overview_retrieval_eval.json&top_k=3",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["entries"][0]["primary_metric_name"] == "hit_rate_at_k"


def test_latest_agent_route_evaluation_endpoint_returns_404_when_missing(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        report_store_service,
        "load_latest_agent_route_report",
        lambda dataset_name: None,
    )

    response = client.get("/api/evaluation/agent-route/latest?dataset_name=agent_route_eval.json")

    assert response.status_code == 404
    assert response.json()["detail"] == "evaluation_report_not_found"


def test_agent_route_evaluation_history_endpoint_returns_entries(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        report_store_service,
        "list_agent_route_report_history",
        lambda dataset_name, limit=5: [
            {
                "dataset_name": dataset_name,
                "saved_at": "2026-03-17T02:05:00+00:00",
                "report_source": "saved",
                "top_k": None,
                "primary_metric_name": "route_accuracy",
                "primary_metric_value": 1.0,
                "case_count": 23,
            }
        ],
    )

    response = client.get("/api/evaluation/agent-route/history?dataset_name=agent_route_eval.json")

    assert response.status_code == 200
    assert response.json()["entries"][0]["primary_metric_name"] == "route_accuracy"


def test_latest_agent_workflow_evaluation_endpoint_returns_saved_report(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        report_store_service,
        "load_latest_agent_workflow_report",
        lambda dataset_name: {
            "dataset_name": dataset_name,
            "saved_at": "2026-03-17T02:10:00+00:00",
            "report_source": "saved",
            "report": {
                "summary": {
                    "total_cases": 1,
                    "workflow_accuracy": 1.0,
                },
                "cases": [],
            },
        },
    )

    response = client.get(
        "/api/evaluation/agent-workflow/latest?dataset_name=agent_workflow_eval.json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["report_source"] == "saved"
    assert payload["saved_at"] == "2026-03-17T02:10:00+00:00"


def test_agent_workflow_evaluation_history_endpoint_returns_entries(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        report_store_service,
        "list_agent_workflow_report_history",
        lambda dataset_name, limit=5: [
            {
                "dataset_name": dataset_name,
                "saved_at": "2026-03-17T02:10:00+00:00",
                "report_source": "saved",
                "top_k": None,
                "primary_metric_name": "workflow_accuracy",
                "primary_metric_value": 0.9,
                "case_count": 30,
            }
        ],
    )

    response = client.get(
        "/api/evaluation/agent-workflow/history?dataset_name=agent_workflow_eval.json",
    )

    assert response.status_code == 200
    assert response.json()["entries"][0]["primary_metric_name"] == "workflow_accuracy"


def test_latest_tool_execution_evaluation_endpoint_returns_saved_report(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        report_store_service,
        "load_latest_tool_execution_report",
        lambda dataset_name: {
            "dataset_name": dataset_name,
            "saved_at": "2026-03-17T02:20:00+00:00",
            "report_source": "saved",
            "report": {
                "summary": {
                    "total_cases": 5,
                    "tool_accuracy": 0.8,
                },
                "cases": [],
            },
        },
    )

    response = client.get(
        "/api/evaluation/tool-execution/latest?dataset_name=agent_tool_execution_eval.json",
    )

    assert response.status_code == 200
    assert response.json()["report_source"] == "saved"


def test_tool_execution_evaluation_history_endpoint_returns_entries(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        report_store_service,
        "list_tool_execution_report_history",
        lambda dataset_name, limit=5: [
            {
                "dataset_name": dataset_name,
                "saved_at": "2026-03-17T02:20:00+00:00",
                "report_source": "saved",
                "top_k": None,
                "primary_metric_name": "tool_accuracy",
                "primary_metric_value": 0.8,
                "case_count": 5,
            }
        ],
    )

    response = client.get(
        "/api/evaluation/tool-execution/history?dataset_name=agent_tool_execution_eval.json",
    )

    assert response.status_code == 200
    assert response.json()["entries"][0]["primary_metric_name"] == "tool_accuracy"
