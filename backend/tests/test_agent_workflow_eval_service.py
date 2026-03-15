import json

from app.services.evaluation.agent_workflow_eval_service import evaluate_agent_workflow_dataset
from app.services.indexing import embedding_service
from app.core.config import settings


def test_evaluate_agent_workflow_dataset_computes_workflow_accuracy(
    workspace_tmp_path,
    monkeypatch,
):
    embedding_dir = workspace_tmp_path / "embeddings"
    embedding_dir.mkdir()
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    dataset_path = workspace_tmp_path / "agent_workflow_eval.json"
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"
    ticket_store_path = workspace_tmp_path / "tickets.json"

    monkeypatch.setattr(embedding_service, "EMBEDDING_DATA_DIR", embedding_dir)
    monkeypatch.setattr(settings, "chat_provider", "fallback")
    monkeypatch.setattr("app.services.ingestion.document_service.RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    embedding_payload = {
        "filename": "sample.txt",
        "suffix": ".txt",
        "embedding_provider": "mock",
        "embedding_model": "mock-embedding-v1",
        "vector_dim": 8,
        "source_path": "../data/raw/sample.txt",
        "source_chunk_path": "../data/chunks/sample.chunks.json",
        "created_at": "2026-03-14T00:00:00+00:00",
        "pipeline_version": "indexing-v1",
        "chunk_count": 1,
        "embeddings": [
            {
                "embedding_id": "sample.txt::chunk_0::embedding",
                "chunk_id": "sample.txt::chunk_0",
                "chunk_index": 0,
                "source_filename": "sample.txt",
                "source_suffix": ".txt",
                "char_count": 11,
                "content": "rag systems",
                "vector": embedding_service.build_mock_embedding("rag systems"),
            }
        ],
    }
    (embedding_dir / "sample.embeddings.json").write_text(
        json.dumps(embedding_payload),
        encoding="utf-8",
    )
    (raw_dir / "sample.txt").write_text(
        "RAG systems combine retrieval and generation.\n\n"
        "Reranking improves candidate ordering for relevant chunks.",
        encoding="utf-8",
    )

    dataset_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case_1",
                        "question": "What are rag systems?",
                        "filename": "sample.txt",
                        "top_k": 1,
                        "expected_route_type": "knowledge_retrieval",
                        "expected_workflow_status": "completed",
                    },
                    {
                        "case_id": "case_2",
                        "question": "Create a ticket for the payment service outage",
                        "expected_route_type": "tool_execution",
                        "expected_workflow_status": "completed",
                        "expected_tool_chain_length": 1,
                        "expected_final_tool_name": "ticketing",
                        "expected_final_action": "create",
                        "expected_final_output_keys": ["ticket_id", "status"],
                    },
                    {
                        "case_id": "case_3",
                        "question": "Search docs for RAG",
                        "expected_route_type": "tool_execution",
                        "expected_workflow_status": "completed",
                    },
                    {
                        "case_id": "case_4",
                        "question": "Check system status",
                        "expected_route_type": "tool_execution",
                        "expected_workflow_status": "completed",
                    },
                    {
                        "case_id": "case_5",
                        "question": "Close ticket TICKET-0007 for payment-service",
                        "expected_route_type": "tool_execution",
                        "expected_workflow_status": "completed",
                    },
                    {
                        "case_id": "case_6",
                        "question": "Update ticket TICKET-0009 for checkout-api to high severity",
                        "expected_route_type": "tool_execution",
                        "expected_workflow_status": "completed",
                    },
                    {
                        "case_id": "case_7",
                        "question": "Set ticket TICKET-0003 severity to medium",
                        "expected_route_type": "tool_execution",
                        "expected_workflow_status": "completed",
                    },
                    {
                        "case_id": "case_8",
                        "question": "Move ticket TICKET-0004 for payment-service to staging",
                        "expected_route_type": "tool_execution",
                        "expected_workflow_status": "completed",
                    },
                    {
                        "case_id": "case_9",
                        "question": "Update ticket TICKET-0010 for payment-service status to closed",
                        "expected_route_type": "tool_execution",
                        "expected_workflow_status": "completed",
                    },
                    {
                        "case_id": "case_10",
                        "question": "Search docs for RAG and create a high severity ticket for payment-service",
                        "expected_route_type": "tool_execution",
                        "expected_workflow_status": "completed",
                        "expected_tool_chain_length": 2,
                        "expected_final_tool_name": "ticketing",
                        "expected_final_action": "create",
                        "expected_final_output_keys": ["ticket_id", "supporting_query", "supporting_summary"],
                    },
                    {
                        "case_id": "case_11",
                        "question": "Search docs for RAG and show top 1 results",
                        "expected_route_type": "tool_execution",
                        "expected_workflow_status": "completed",
                        "expected_tool_chain_length": 1,
                        "expected_final_tool_name": "document_search",
                        "expected_final_action": "query",
                        "expected_final_output_keys": ["returned_count", "max_results", "top_match_document"],
                    },
                    {
                        "case_id": "case_12",
                        "question": "Search rag_overview.md for reranking limit to 1",
                        "expected_route_type": "tool_execution",
                        "expected_workflow_status": "completed",
                        "expected_tool_chain_length": 1,
                        "expected_final_tool_name": "document_search",
                        "expected_final_action": "query",
                        "expected_final_output_keys": ["filename_filter", "max_results", "matched_documents"],
                    },
                    {
                        "case_id": "case_13",
                        "question": "Search docs for RAG and summarize top 1 results",
                        "expected_route_type": "tool_execution",
                        "expected_workflow_status": "completed",
                        "expected_tool_chain_length": 1,
                        "expected_final_tool_name": "document_search",
                        "expected_final_action": "query",
                        "expected_final_output_keys": ["returned_count", "top_match_document"],
                    },
                    {
                        "case_id": "case_14",
                        "question": "Search docs for payment-service outage and summarize top 1 results",
                        "expected_route_type": "tool_execution",
                        "expected_workflow_status": "clarification_required",
                        "expected_tool_chain_length": 1,
                        "expected_final_tool_name": "document_search",
                        "expected_final_action": "query",
                        "expected_final_output_keys": ["matched_count"],
                    },
                    {
                        "case_id": "case_15",
                        "question": "Search docs for payment-service outage and create a high severity ticket for payment-service",
                        "expected_route_type": "tool_execution",
                        "expected_workflow_status": "clarification_required",
                        "expected_tool_chain_length": 1,
                        "expected_final_tool_name": "document_search",
                        "expected_final_action": "query",
                        "expected_final_output_keys": ["matched_count"],
                    },
                    {
                        "case_id": "case_16",
                        "question": "Search docs for payment-service outage and summarize top 1 results",
                        "clarification_context": {
                            "search_query_refinement": "RAG",
                            "document_scope": "sample.txt",
                        },
                        "resume_via_run_id": True,
                        "filename": "sample.txt",
                        "top_k": 1,
                        "expected_route_type": "tool_execution",
                        "expected_workflow_status": "completed",
                        "expected_question": "Search sample.txt for RAG and summarize top 1 results",
                        "expected_resume_trace": True,
                        "expected_tool_chain_length": 1,
                        "expected_final_tool_name": "document_search",
                        "expected_final_action": "query",
                        "expected_final_output_keys": ["filename_filter", "returned_count"],
                    },
                    {
                        "case_id": "case_17",
                        "question": "Search docs for payment-service outage and create a high severity ticket for payment-service",
                        "clarification_context": {
                            "execution_confirmation": "yes",
                            "environment": "production",
                        },
                        "expected_route_type": "tool_execution",
                        "expected_workflow_status": "completed",
                        "expected_question": "Search docs for payment-service outage and create a high severity ticket for payment-service in production",
                        "expected_resume_trace": True,
                        "expected_tool_chain_length": 2,
                        "expected_final_tool_name": "ticketing",
                        "expected_final_action": "create",
                        "expected_final_output_keys": ["ticket_id", "environment"],
                    },
                    {
                        "case_id": "case_18",
                        "question": "Please do that for production",
                        "expected_route_type": "clarification_needed",
                        "expected_workflow_status": "clarification_required",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    report = evaluate_agent_workflow_dataset(dataset_path=dataset_path)

    assert report.summary.total_cases == 18
    assert report.summary.workflow_accuracy == 1.0
    assert all(case.matched for case in report.cases)
    multistep_case = next(case for case in report.cases if case.case_id == "case_10")
    assert multistep_case.actual_tool_chain_length == 2
    assert multistep_case.actual_final_tool_name == "ticketing"
    assert multistep_case.final_output_key_matches["supporting_summary"] is True
    capped_search_case = next(case for case in report.cases if case.case_id == "case_11")
    assert capped_search_case.actual_tool_chain_length == 1
    assert capped_search_case.actual_final_tool_name == "document_search"
    assert capped_search_case.final_output_key_matches["max_results"] is True
    filename_scoped_case = next(case for case in report.cases if case.case_id == "case_12")
    assert filename_scoped_case.actual_tool_chain_length == 1
    assert filename_scoped_case.actual_final_tool_name == "document_search"
    assert filename_scoped_case.final_output_key_matches["filename_filter"] is True
    summarize_case = next(case for case in report.cases if case.case_id == "case_13")
    assert summarize_case.actual_tool_chain_length == 1
    assert summarize_case.actual_final_tool_name == "document_search"
    assert summarize_case.final_output_key_matches["returned_count"] is True
    resumed_case = next(case for case in report.cases if case.case_id == "case_16")
    assert resumed_case.actual_question == "Search sample.txt for RAG and summarize top 1 results"
    assert resumed_case.resume_trace_present is True
    assert resumed_case.final_output_key_matches["filename_filter"] is True
    confirmed_resume_case = next(case for case in report.cases if case.case_id == "case_17")
    assert confirmed_resume_case.actual_question == (
        "Search docs for payment-service outage and create a high severity ticket for payment-service in production"
    )
    assert confirmed_resume_case.resume_trace_present is True
    assert confirmed_resume_case.final_output_key_matches["environment"] is True
