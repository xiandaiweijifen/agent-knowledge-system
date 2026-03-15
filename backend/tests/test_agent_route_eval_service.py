import json

from app.services.evaluation.agent_route_eval_service import evaluate_agent_route_dataset


def test_evaluate_agent_route_dataset_computes_route_accuracy(workspace_tmp_path):
    dataset_path = workspace_tmp_path / "agent_route_eval.json"
    dataset_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case_1",
                        "question": "What is RAG?",
                        "filename": "rag_overview.md",
                        "expected_route_type": "knowledge_retrieval",
                    },
                    {
                        "case_id": "case_2",
                        "question": "Create a ticket for the payment service outage",
                        "expected_route_type": "tool_execution",
                    },
                    {
                        "case_id": "case_3",
                        "question": "Search docs for RAG",
                        "expected_route_type": "tool_execution",
                    },
                    {
                        "case_id": "case_4",
                        "question": "Check system status",
                        "expected_route_type": "tool_execution",
                    },
                    {
                        "case_id": "case_5",
                        "question": "Close ticket TICKET-0007 for payment-service",
                        "expected_route_type": "tool_execution",
                    },
                    {
                        "case_id": "case_6",
                        "question": "Update ticket TICKET-0009 for checkout-api to high severity",
                        "expected_route_type": "tool_execution",
                    },
                    {
                        "case_id": "case_7",
                        "question": "Set ticket TICKET-0003 severity to medium",
                        "expected_route_type": "tool_execution",
                    },
                    {
                        "case_id": "case_8",
                        "question": "Move ticket TICKET-0004 for payment-service to staging",
                        "expected_route_type": "tool_execution",
                    },
                    {
                        "case_id": "case_9",
                        "question": "Update ticket TICKET-0010 for payment-service status to closed",
                        "expected_route_type": "tool_execution",
                    },
                    {
                        "case_id": "case_10",
                        "question": "Search docs for RAG and create a high severity ticket for payment-service",
                        "expected_route_type": "tool_execution",
                    },
                    {
                        "case_id": "case_11",
                        "question": "Search docs for payment-service outage and create a high severity ticket for payment-service",
                        "expected_route_type": "tool_execution",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    report = evaluate_agent_route_dataset(dataset_path=dataset_path)

    assert report.summary.total_cases == 11
    assert report.summary.route_accuracy == 1.0
    assert all(case.matched for case in report.cases)
