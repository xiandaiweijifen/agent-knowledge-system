import json

from app.services.evaluation.tool_execution_eval_service import evaluate_tool_execution_dataset
from app.services.ingestion import document_service


def test_evaluate_tool_execution_dataset_computes_tool_accuracy(
    workspace_tmp_path,
    monkeypatch,
):
    dataset_path = workspace_tmp_path / "agent_tool_execution_eval.json"
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text("RAG systems improve retrieval grounding.", encoding="utf-8")
    ticket_store_path = workspace_tmp_path / "tickets.json"

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    dataset_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case_1",
                        "question": "Search docs for RAG",
                        "expected_tool_name": "document_search",
                        "expected_action": "query",
                        "expected_execution_status": "completed",
                        "expected_output_keys": ["query", "matched_count", "matched_documents"],
                    },
                    {
                        "case_id": "case_2",
                        "question": "Create a high severity ticket for payment-service in production",
                        "expected_tool_name": "ticketing",
                        "expected_action": "create",
                        "expected_execution_status": "completed",
                        "expected_arguments": {
                            "severity": "high",
                            "environment": "production",
                        },
                        "expected_output": {
                            "status": "open",
                            "severity": "high",
                            "environment": "production",
                        },
                        "expected_output_keys": ["ticket_id", "created_at"],
                    },
                    {
                        "case_id": "case_2b",
                        "question": "List open tickets",
                        "expected_tool_name": "ticketing",
                        "expected_action": "list",
                        "expected_execution_status": "completed",
                        "expected_arguments": {
                            "status": "open",
                        },
                        "expected_output": {
                            "output_kind": "collection",
                        },
                        "expected_output_keys": ["ticket_records", "ticket_ids", "tickets_json"],
                    },
                    {
                        "case_id": "case_3",
                        "question": "Search docs for RAG and show top 1 results",
                        "expected_tool_name": "document_search",
                        "expected_action": "query",
                        "expected_execution_status": "completed",
                        "expected_arguments": {
                            "max_results": "1",
                        },
                        "expected_output": {
                            "max_results": "1",
                        },
                        "expected_output_keys": ["returned_count", "top_match_document"],
                    },
                    {
                        "case_id": "case_4",
                        "question": "Search rag_overview.md for reranking limit to 1",
                        "expected_tool_name": "document_search",
                        "expected_action": "query",
                        "expected_execution_status": "completed",
                        "expected_arguments": {
                            "filename": "rag_overview.md",
                            "max_results": "1",
                        },
                        "expected_output": {
                            "filename_filter": "rag_overview.md",
                            "max_results": "1",
                        },
                        "expected_output_keys": ["matched_documents", "returned_count"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    report = evaluate_tool_execution_dataset(dataset_path=dataset_path)

    assert report.summary.total_cases == 5
    assert report.summary.tool_accuracy == 1.0
    assert all(case.matched for case in report.cases)
