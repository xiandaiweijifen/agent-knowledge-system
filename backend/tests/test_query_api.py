import json

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.agent.router_service import route_request
from app.services.agent.tool_service import (
    execute_tool_request,
    list_registered_tools,
    plan_tool_request,
)
from app.services.llm.workflow_planner_service import (
    _extract_gemini_workflow_plan_text,
    _generate_gemini_workflow_plan,
    _parse_llm_workflow_plan_response,
    generate_llm_workflow_plan,
)
from app.services.llm.tool_planner_service import generate_llm_tool_plan
from app.services.llm.clarification_planner_service import generate_llm_clarification_plan
from app.services.agent.clarification_service import (
    plan_clarification,
    plan_search_miss_clarification,
)
from app.services.ingestion import document_service
from app.services.indexing import embedding_service
from app.services.retrieval.retrieval_service import compute_rerank_bonus
from app.schemas.tools import ToolExecutionRequest


def test_query_endpoint_returns_fallback_answer_with_retrieval_results(
    workspace_tmp_path,
    monkeypatch,
):
    embedding_dir = workspace_tmp_path / "embeddings"
    embedding_dir.mkdir()

    monkeypatch.setattr(embedding_service, "EMBEDDING_DATA_DIR", embedding_dir)
    monkeypatch.setattr(settings, "chat_provider", "fallback")

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
        "chunk_count": 2,
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
            },
            {
                "embedding_id": "sample.txt::chunk_1::embedding",
                "chunk_id": "sample.txt::chunk_1",
                "chunk_index": 1,
                "source_filename": "sample.txt",
                "source_suffix": ".txt",
                "char_count": 10,
                "content": "data lake",
                "vector": embedding_service.build_mock_embedding("data lake"),
            },
        ],
    }
    (embedding_dir / "sample.embeddings.json").write_text(
        json.dumps(embedding_payload),
        encoding="utf-8",
    )

    client = TestClient(app)
    response = client.post(
        "/api/query",
        json={
            "filename": "sample.txt",
            "question": "rag systems",
            "top_k": 1,
        },
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["filename"] == "sample.txt"
    assert payload["answer_source"] == "fallback"
    assert payload["model"] == "local-fallback"
    assert payload["answered_at"]
    assert payload["answer_latency_ms"] >= 0
    assert payload["chat_provider"] == "fallback"
    assert payload["chat_model"] == "local-fallback"
    assert payload["retrieval"]["top_k"] == 1
    assert payload["retrieval"]["embedding_provider"] == "mock"
    assert payload["retrieval"]["embedding_model"] == "mock-embedding-v1"
    assert payload["retrieval"]["vector_dim"] == 8
    assert payload["retrieval"]["query_embedding_provider"] == "mock"
    assert payload["retrieval"]["query_embedding_model"] == "mock-embedding-v1"
    assert payload["retrieval"]["retrieved_at"]
    assert payload["retrieval"]["retrieval_latency_ms"] >= 0
    assert len(payload["retrieval"]["matches"]) == 1
    assert payload["retrieval"]["matches"][0]["chunk_id"] == "sample.txt::chunk_0"
    assert payload["retrieval"]["matches"][0]["score"] >= payload["retrieval"]["matches"][0]["vector_score"]


def test_query_diagnostics_endpoint_returns_ranked_candidates(
    workspace_tmp_path,
    monkeypatch,
):
    embedding_dir = workspace_tmp_path / "embeddings"
    embedding_dir.mkdir()

    monkeypatch.setattr(embedding_service, "EMBEDDING_DATA_DIR", embedding_dir)
    monkeypatch.setattr(settings, "chat_provider", "fallback")

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
        "chunk_count": 3,
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
            },
            {
                "embedding_id": "sample.txt::chunk_1::embedding",
                "chunk_id": "sample.txt::chunk_1",
                "chunk_index": 1,
                "source_filename": "sample.txt",
                "source_suffix": ".txt",
                "char_count": 10,
                "content": "data lake",
                "vector": embedding_service.build_mock_embedding("data lake"),
            },
            {
                "embedding_id": "sample.txt::chunk_2::embedding",
                "chunk_id": "sample.txt::chunk_2",
                "chunk_index": 2,
                "source_filename": "sample.txt",
                "source_suffix": ".txt",
                "char_count": 12,
                "content": "agent system",
                "vector": embedding_service.build_mock_embedding("agent system"),
            },
        ],
    }
    (embedding_dir / "sample.embeddings.json").write_text(
        json.dumps(embedding_payload),
        encoding="utf-8",
    )

    client = TestClient(app)
    response = client.post(
        "/api/query/diagnostics",
        json={
            "filename": "sample.txt",
            "question": "rag systems",
            "top_k": 2,
            "candidate_count": 3,
        },
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["filename"] == "sample.txt"
    assert payload["retrieval"]["top_k"] == 2
    assert len(payload["retrieval"]["matches"]) == 2
    assert len(payload["candidates"]) == 3
    assert payload["candidates"][0]["chunk_id"] == "sample.txt::chunk_0"
    assert payload["candidates"][0]["score"] >= payload["candidates"][0]["vector_score"]
    assert payload["diagnostics"]["returned_candidate_count"] == 3
    assert payload["diagnostics"]["total_scored_chunks"] == 3
    assert payload["diagnostics"]["max_score"] >= payload["diagnostics"]["min_score"]


def test_definition_query_gets_higher_bonus_for_definition_chunk():
    definition_chunk = (
        "# Retrieval-Augmented Generation Overview\n\n"
        "## What RAG Means\n\n"
        "Retrieval-augmented generation, or RAG, is a system pattern."
    )
    generic_chunk = (
        "An enterprise agent system can use RAG as a knowledge layer "
        "for retrieval and tool use."
    )

    definition_bonus = compute_rerank_bonus("What is RAG?", definition_chunk)
    generic_bonus = compute_rerank_bonus("What is RAG?", generic_chunk)

    assert definition_bonus > generic_bonus


def test_reranking_query_gets_higher_bonus_for_reranking_chunk():
    reranking_chunk = (
        "The first retrieval stage usually returns a set of candidate chunks.\n\n"
        "## Retrieval and Reranking\n\n"
        "Many production systems then apply a reranker to reorder the candidates."
    )
    generic_chunk = (
        "A strong RAG system needs evaluation and observability. Engineers should "
        "track retrieval latency and answer latency."
    )

    reranking_bonus = compute_rerank_bonus(
        "Why do production systems use reranking?",
        reranking_chunk,
    )
    generic_bonus = compute_rerank_bonus(
        "Why do production systems use reranking?",
        generic_chunk,
    )

    assert reranking_bonus > generic_bonus


def test_route_request_classifies_tool_execution():
    decision = route_request("Create a ticket for the payment service outage")

    assert decision.route_type == "tool_execution"


def test_route_request_classifies_document_search_as_tool_execution():
    decision = route_request("Search docs for RAG")

    assert decision.route_type == "tool_execution"


def test_route_request_classifies_look_up_document_search_as_tool_execution():
    decision = route_request("Look up docs about RAG, then summarize the top 2 results")

    assert decision.route_type == "tool_execution"


def test_route_request_classifies_clarification_needed():
    decision = route_request("Please do that for production")

    assert decision.route_type == "clarification_needed"


def test_query_route_endpoint_returns_route_decision():
    client = TestClient(app)
    response = client.post(
        "/api/query/route",
        json={
            "question": "What is RAG?",
            "filename": "rag_overview.md",
        },
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["route_type"] == "knowledge_retrieval"
    assert payload["filename"] == "rag_overview.md"
    assert payload["route_reason"]


def test_execute_tool_request_returns_stubbed_result(workspace_tmp_path, monkeypatch):
    ticket_store_path = workspace_tmp_path / "tickets.json"
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    response = execute_tool_request(
        ToolExecutionRequest(
            tool_name="ticketing",
            action="create",
            target="payment-service",
            arguments={"severity": "high"},
        )
    )

    assert response.execution_status == "completed"
    assert response.execution_mode == "local_adapter"
    assert response.trace_id
    assert response.output["ticket_id"].startswith("TICKET-")


def test_execute_ticketing_tool_supports_create_update_close(workspace_tmp_path, monkeypatch):
    ticket_store_path = workspace_tmp_path / "tickets.json"
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    created = execute_tool_request(
        ToolExecutionRequest(
            tool_name="ticketing",
            action="create",
            target="payment-service",
            arguments={"severity": "high", "environment": "production"},
        )
    )
    ticket_id = created.output["ticket_id"]

    updated = execute_tool_request(
        ToolExecutionRequest(
            tool_name="ticketing",
            action="update",
            target="payment-service",
            arguments={"ticket_id": ticket_id, "severity": "medium"},
        )
    )

    closed = execute_tool_request(
        ToolExecutionRequest(
            tool_name="ticketing",
            action="close",
            target="payment-service",
            arguments={"ticket_id": ticket_id},
        )
    )

    reopened = execute_tool_request(
        ToolExecutionRequest(
            tool_name="ticketing",
            action="update",
            target="payment-service",
            arguments={"ticket_id": ticket_id, "status": "open"},
        )
    )

    assert created.execution_status == "completed"
    assert created.output["schema_version"] == "tool-output-v1"
    assert created.output["output_kind"] == "record"
    assert created.output["resource_type"] == "ticket"
    assert created.output["resource_id"] == ticket_id
    assert created.output["status"] == "open"
    assert updated.output["severity"] == "medium"
    assert closed.output["status"] == "closed"
    assert "closed_at" in closed.output
    assert reopened.output["status"] == "open"
    assert "closed_at" not in reopened.output


def test_execute_ticketing_tool_builds_supporting_summary_from_search_context(
    workspace_tmp_path,
    monkeypatch,
):
    ticket_store_path = workspace_tmp_path / "tickets.json"
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    created = execute_tool_request(
        ToolExecutionRequest(
            tool_name="ticketing",
            action="create",
            target="payment-service",
            arguments={
                "severity": "high",
                "supporting_query": "RAG",
                "supporting_documents": "rag_overview.md, test_chunk.txt",
                "supporting_snippets": "rag_overview.md: Retrieval-augmented generation, or RAG, is ...",
                "supporting_match_count": "2",
            },
        )
    )

    assert created.output["supporting_summary"].startswith("Search for 'RAG' matched 2 supporting document")
    assert "rag_overview.md" in created.output["supporting_summary"]
    assert created.output["schema_version"] == "tool-output-v1"
    assert created.output["resource_type"] == "ticket"


def test_execute_ticketing_tool_supports_query(workspace_tmp_path, monkeypatch):
    ticket_store_path = workspace_tmp_path / "tickets.json"
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    created = execute_tool_request(
        ToolExecutionRequest(
            tool_name="ticketing",
            action="create",
            target="payment-service",
            arguments={"severity": "high", "environment": "production"},
        )
    )

    queried = execute_tool_request(
        ToolExecutionRequest(
            tool_name="ticketing",
            action="query",
            target="payment-service",
            arguments={"ticket_id": created.output["ticket_id"]},
        )
    )

    assert queried.execution_status == "completed"
    assert queried.execution_mode == "local_adapter"
    assert queried.output["schema_version"] == "tool-output-v1"
    assert queried.output["resource_id"] == created.output["ticket_id"]
    assert queried.output["ticket_id"] == created.output["ticket_id"]
    assert queried.output["status"] == "open"


def test_execute_ticketing_tool_create_recovers_from_invalid_ticket_store(
    workspace_tmp_path,
    monkeypatch,
):
    ticket_store_path = workspace_tmp_path / "tickets.json"
    ticket_store_path.write_text("{invalid json", encoding="utf-8")
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    created = execute_tool_request(
        ToolExecutionRequest(
            tool_name="ticketing",
            action="create",
            target="payment-service",
            arguments={"severity": "high"},
        )
    )

    assert created.execution_status == "completed"
    assert created.output["ticket_id"] == "TICKET-0001"
    persisted_tickets = json.loads(ticket_store_path.read_text(encoding="utf-8"))
    assert len(persisted_tickets) == 1
    assert persisted_tickets[0]["ticket_id"] == "TICKET-0001"


def test_execute_ticketing_tool_normalizes_legacy_ticket_record_on_query(
    workspace_tmp_path,
    monkeypatch,
):
    ticket_store_path = workspace_tmp_path / "tickets.json"
    ticket_store_path.write_text(
        json.dumps(
            [
                {
                    "ticket_id": "TICKET-0001",
                    "target": "payment-service",
                    "status": "open",
                    "severity": "high",
                    "environment": "production",
                    "created_at": "2026-03-15T00:00:00+00:00",
                    "updated_at": "2026-03-15T00:00:00+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    queried = execute_tool_request(
        ToolExecutionRequest(
            tool_name="ticketing",
            action="query",
            target="payment-service",
            arguments={"ticket_id": "TICKET-0001"},
        )
    )

    assert queried.execution_status == "completed"
    assert queried.output["schema_version"] == "tool-output-v1"
    assert queried.output["resource_type"] == "ticket"
    assert queried.output["resource_id"] == "TICKET-0001"


def test_execute_ticketing_tool_supports_list(workspace_tmp_path, monkeypatch):
    ticket_store_path = workspace_tmp_path / "tickets.json"
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    execute_tool_request(
        ToolExecutionRequest(
            tool_name="ticketing",
            action="create",
            target="payment-service",
            arguments={"severity": "high", "environment": "production"},
        )
    )
    execute_tool_request(
        ToolExecutionRequest(
            tool_name="ticketing",
            action="create",
            target="checkout-api",
            arguments={"severity": "medium", "environment": "staging"},
        )
    )

    listed = execute_tool_request(
        ToolExecutionRequest(
            tool_name="ticketing",
            action="list",
            target="tickets",
            arguments={"status": "open"},
        )
    )

    assert listed.execution_status == "completed"
    assert listed.execution_mode == "local_adapter"
    assert listed.output["schema_version"] == "tool-output-v1"
    assert listed.output["output_kind"] == "collection"
    assert listed.output["resource_type"] == "ticket"
    assert listed.output["item_count"] == "2"
    assert listed.output["ticket_count"] == "2"
    assert listed.output["matched_count"] == "2"
    assert listed.output["sort_by"] == "updated_at"
    assert listed.output["sort_order"] == "desc"
    assert listed.output["ticket_ids"] == "TICKET-0002, TICKET-0001"
    listed_records = json.loads(listed.output["tickets_json"])
    assert len(listed_records) == 2
    assert listed.output["ticket_records"][0]["ticket_id"] == "TICKET-0002"
    assert listed.output["ticket_records"][0]["status"] == "open"
    assert listed.output["ticket_records"] == listed_records
    assert listed.output["status_filter"] == "open"
    assert listed.output["tickets"].startswith("TICKET-0002")


def test_execute_ticketing_tool_filters_list_by_canonical_target(
    workspace_tmp_path,
    monkeypatch,
):
    ticket_store_path = workspace_tmp_path / "tickets.json"
    ticket_store_path.write_text(
        json.dumps(
            [
                {
                    "ticket_id": "TICKET-0001",
                    "target": "the payment service outage",
                    "status": "open",
                    "severity": "high",
                    "environment": "production",
                    "created_at": "2026-03-15T00:00:00+00:00",
                    "updated_at": "2026-03-15T00:00:00+00:00",
                },
                {
                    "ticket_id": "TICKET-0002",
                    "target": "checkout-api",
                    "status": "open",
                    "severity": "medium",
                    "environment": "staging",
                    "created_at": "2026-03-15T00:00:00+00:00",
                    "updated_at": "2026-03-15T00:00:00+00:00",
                },
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    listed = execute_tool_request(
        ToolExecutionRequest(
            tool_name="ticketing",
            action="list",
            target="tickets",
            arguments={"status": "open", "target_filter": "payment-service"},
        )
    )

    assert listed.execution_status == "completed"
    assert listed.output["ticket_count"] == "1"
    assert listed.output["target_filter"] == "payment-service"
    assert listed.output["ticket_records"][0]["ticket_id"] == "TICKET-0001"
    assert listed.output["ticket_records"][0]["target"] == "payment-service"


def test_execute_ticketing_tool_route_preserves_target_filter(
    workspace_tmp_path,
    monkeypatch,
):
    ticket_store_path = workspace_tmp_path / "tickets.json"
    ticket_store_path.write_text(
        json.dumps(
            [
                {
                    "ticket_id": "TICKET-0001",
                    "target": "the payment service outage",
                    "status": "open",
                    "severity": "high",
                    "environment": "production",
                    "created_at": "2026-03-15T00:00:00+00:00",
                    "updated_at": "2026-03-15T00:00:00+00:00",
                },
                {
                    "ticket_id": "TICKET-0002",
                    "target": "checkout-api",
                    "status": "open",
                    "severity": "medium",
                    "environment": "staging",
                    "created_at": "2026-03-15T00:00:00+00:00",
                    "updated_at": "2026-03-15T00:00:00+00:00",
                },
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    client = TestClient(app)
    response = client.post(
        "/api/query/tools/execute",
        json={
            "tool_name": "ticketing",
            "action": "list",
            "target": "tickets",
            "arguments": {
                "status": "open",
                "target_filter": "payment-service",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["output"]["ticket_count"] == "1"
    assert payload["output"]["target_filter"] == "payment-service"
    assert payload["output"]["ticket_records"][0]["ticket_id"] == "TICKET-0001"
    assert payload["output"]["ticket_records"][0]["target"] == "payment-service"


def test_execute_ticketing_tool_filters_list_by_combined_fields(
    workspace_tmp_path,
    monkeypatch,
):
    ticket_store_path = workspace_tmp_path / "tickets.json"
    ticket_store_path.write_text(
        json.dumps(
            [
                {
                    "ticket_id": "TICKET-0001",
                    "target": "the payment service outage",
                    "status": "open",
                    "severity": "high",
                    "environment": "production",
                    "created_at": "2026-03-15T00:00:00+00:00",
                    "updated_at": "2026-03-15T00:00:00+00:00",
                },
                {
                    "ticket_id": "TICKET-0002",
                    "target": "payment-service",
                    "status": "open",
                    "severity": "high",
                    "environment": "staging",
                    "created_at": "2026-03-15T00:00:00+00:00",
                    "updated_at": "2026-03-15T00:00:00+00:00",
                },
                {
                    "ticket_id": "TICKET-0003",
                    "target": "checkout-api",
                    "status": "open",
                    "severity": "high",
                    "environment": "production",
                    "created_at": "2026-03-15T00:00:00+00:00",
                    "updated_at": "2026-03-15T00:00:00+00:00",
                },
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    listed = execute_tool_request(
        ToolExecutionRequest(
            tool_name="ticketing",
            action="list",
            target="tickets",
            arguments={
                "status": "open",
                "target_filter": "payment-service",
                "severity_filter": "high",
                "environment_filter": "production",
            },
        )
    )

    assert listed.execution_status == "completed"
    assert listed.output["ticket_count"] == "1"
    assert listed.output["target_filter"] == "payment-service"
    assert listed.output["severity_filter"] == "high"
    assert listed.output["environment_filter"] == "production"
    assert listed.output["ticket_records"][0]["ticket_id"] == "TICKET-0001"
    assert listed.output["ticket_records"][0]["environment"] == "production"


def test_execute_ticketing_tool_list_honors_max_results_and_latest_order(
    workspace_tmp_path,
    monkeypatch,
):
    ticket_store_path = workspace_tmp_path / "tickets.json"
    ticket_store_path.write_text(
        json.dumps(
            [
                {
                    "ticket_id": "TICKET-0001",
                    "target": "payment-service",
                    "status": "open",
                    "severity": "high",
                    "environment": "production",
                    "created_at": "2026-03-15T00:00:00+00:00",
                    "updated_at": "2026-03-15T00:00:00+00:00",
                },
                {
                    "ticket_id": "TICKET-0002",
                    "target": "payment-service",
                    "status": "open",
                    "severity": "high",
                    "environment": "production",
                    "created_at": "2026-03-15T01:00:00+00:00",
                    "updated_at": "2026-03-15T01:00:00+00:00",
                },
                {
                    "ticket_id": "TICKET-0003",
                    "target": "payment-service",
                    "status": "open",
                    "severity": "high",
                    "environment": "production",
                    "created_at": "2026-03-15T02:00:00+00:00",
                    "updated_at": "2026-03-15T02:00:00+00:00",
                },
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    listed = execute_tool_request(
        ToolExecutionRequest(
            tool_name="ticketing",
            action="list",
            target="tickets",
            arguments={"status": "open", "max_results": "2"},
        )
    )

    assert listed.execution_status == "completed"
    assert listed.output["matched_count"] == "3"
    assert listed.output["item_count"] == "2"
    assert listed.output["ticket_count"] == "2"
    assert listed.output["max_results"] == "2"
    assert listed.output["ticket_ids"] == "TICKET-0003, TICKET-0002"
    assert [ticket["ticket_id"] for ticket in listed.output["ticket_records"]] == [
        "TICKET-0003",
        "TICKET-0002",
    ]


def test_execute_system_status_tool_returns_live_local_snapshot(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "embedding_provider", "gemini")
    monkeypatch.setattr(settings, "chat_provider", "fallback")
    monkeypatch.setattr(settings, "gemini_api_key", "configured")
    monkeypatch.setattr(settings, "openai_api_key", "")

    response = execute_tool_request(
        ToolExecutionRequest(
            tool_name="system_status",
            action="query",
            target="agent-knowledge-system",
            arguments={},
        )
    )

    assert response.execution_status == "completed"
    assert response.execution_mode == "local_adapter"
    assert response.output["schema_version"] == "tool-output-v1"
    assert response.output["output_kind"] == "status_snapshot"
    assert response.output["resource_type"] == "system_status"
    assert response.output["target"] == "agent-knowledge-system"
    assert response.output["embedding_provider"] == "gemini"
    assert response.output["chat_provider"] == "fallback"
    assert response.output["gemini_configured"] == "true"


def test_execute_system_status_tool_preserves_requested_target(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")

    response = execute_tool_request(
        ToolExecutionRequest(
            tool_name="system_status",
            action="query",
            target="payment-service",
            arguments={},
        )
    )

    assert response.execution_status == "completed"
    assert response.output["target"] == "payment-service"
    assert response.output["status"] == "ok"


def test_execute_system_status_tool_preserves_requested_environment(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")

    response = execute_tool_request(
        ToolExecutionRequest(
            tool_name="system_status",
            action="query",
            target="payment-service",
            arguments={"environment": "production"},
        )
    )

    assert response.execution_status == "completed"
    assert response.output["target"] == "payment-service"
    assert response.output["app_env"] == "development"
    assert response.output["requested_environment"] == "production"
    assert "requested environment production" in response.result_summary


def test_execute_document_search_tool_returns_local_matches(workspace_tmp_path, monkeypatch):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "notes.md").write_text("RAG systems rely on retrieval and grounding.", encoding="utf-8")
    (raw_dir / "other.md").write_text("This file talks about deployment workflows.", encoding="utf-8")
    (raw_dir / "slides.pdf").write_bytes(b"%PDF-1.7")

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)

    response = execute_tool_request(
        ToolExecutionRequest(
            tool_name="document_search",
            action="query",
            target="retrieval",
            arguments={},
        )
    )

    assert response.execution_status == "completed"
    assert response.execution_mode == "local_adapter"
    assert response.output["schema_version"] == "tool-output-v1"
    assert response.output["output_kind"] == "search_results"
    assert response.output["resource_type"] == "document_match"
    assert response.output["item_count"] == "1"
    assert response.output["matched_count"] == "1"
    assert "notes.md" in response.output["matched_documents"]
    assert response.output["skipped_documents"] == "1"


def test_execute_document_search_tool_returns_filename_filter_when_used(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text("Reranking improves retrieval quality.", encoding="utf-8")
    (raw_dir / "notes.md").write_text("Reranking appears here too.", encoding="utf-8")

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)

    response = execute_tool_request(
        ToolExecutionRequest(
            tool_name="document_search",
            action="query",
            target="reranking",
            arguments={"filename": "rag_overview.md"},
        )
    )

    assert response.execution_status == "completed"
    assert response.output["filename_filter"] == "rag_overview.md"
    assert response.output["matched_documents"] == "rag_overview.md"


def test_execute_document_search_tool_ranks_more_specific_match_first(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text(
        "RAG is a system pattern. Retrieval-augmented generation improves factual grounding.",
        encoding="utf-8",
    )
    (raw_dir / "notes.txt").write_text(
        "This note mentions RAG briefly near the end. Something else first. RAG.",
        encoding="utf-8",
    )

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)

    response = execute_tool_request(
        ToolExecutionRequest(
            tool_name="document_search",
            action="query",
            target="RAG",
            arguments={},
        )
    )

    assert response.execution_status == "completed"
    assert response.output["matched_documents"].split(", ")[0] == "rag_overview.md"
    assert response.output["snippets"].split(" | ")[0].startswith("rag_overview.md:")
    assert response.output["top_match_document"] == "rag_overview.md"
    assert float(response.output["top_match_score"]) > 0
    assert "full query match" in response.output["top_match_reason"]


def test_execute_document_search_tool_returns_clean_sentence_snippets(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text(
        "# Retrieval-Augmented Generation Overview\n"
        "## What RAG Means\n"
        "RAG combines retrieval with generation to improve factual grounding.\n"
        "Extra trailing details follow after the main statement.\n",
        encoding="utf-8",
    )
    (raw_dir / "notes.txt").write_text(
        "Bullet list:\n"
        "- RAG appears in this supporting note.\n"
        "- Another line that should be normalized.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)

    response = execute_tool_request(
        ToolExecutionRequest(
            tool_name="document_search",
            action="query",
            target="RAG",
            arguments={},
        )
    )

    assert response.execution_status == "completed"
    first_snippet = response.output["snippets"].split(" | ")[0]
    second_snippet = response.output["snippets"].split(" | ")[1]
    assert first_snippet == (
        "rag_overview.md: RAG combines retrieval with generation to improve factual grounding."
    )
    assert "## What RAG Means" not in first_snippet
    assert second_snippet.startswith("notes.txt:")
    assert "  " not in second_snippet


def test_execute_document_search_tool_honors_max_results(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text("RAG appears here first and most clearly.", encoding="utf-8")
    (raw_dir / "notes.txt").write_text("RAG is mentioned in this note.", encoding="utf-8")
    (raw_dir / "summary.md").write_text("This summary also mentions RAG in passing.", encoding="utf-8")

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)

    response = execute_tool_request(
        ToolExecutionRequest(
            tool_name="document_search",
            action="query",
            target="RAG",
            arguments={"max_results": "2"},
        )
    )

    assert response.execution_status == "completed"
    assert response.output["matched_count"] == "3"
    assert response.output["returned_count"] == "2"
    assert response.output["max_results"] == "2"
    assert len(response.output["matched_documents"].split(", ")) == 2


def test_query_tool_execute_endpoint_returns_structured_stub(workspace_tmp_path, monkeypatch):
    ticket_store_path = workspace_tmp_path / "tickets.json"
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    client = TestClient(app)
    response = client.post(
        "/api/query/tools/execute",
        json={
            "tool_name": "ticketing",
            "action": "create",
            "target": "payment-service",
            "arguments": {"severity": "high"},
        },
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["tool_name"] == "ticketing"
    assert payload["execution_status"] == "completed"
    assert payload["execution_mode"] == "local_adapter"
    assert payload["trace_id"]
    assert payload["output"]["ticket_id"].startswith("TICKET-")


def test_query_tool_execute_endpoint_returns_live_system_status():
    client = TestClient(app)
    response = client.post(
        "/api/query/tools/execute",
        json={
            "tool_name": "system_status",
            "action": "query",
            "target": "agent-knowledge-system",
            "arguments": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_status"] == "completed"
    assert payload["execution_mode"] == "local_adapter"
    assert "embedding_provider" in payload["output"]


def test_list_registered_tools_returns_catalog():
    catalog = list_registered_tools()

    assert catalog.count >= 3
    assert any(tool.tool_name == "ticketing" for tool in catalog.tools)


def test_query_tools_endpoint_returns_catalog():
    client = TestClient(app)
    response = client.get("/api/query/tools")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] >= 3
    assert any(tool["tool_name"] == "ticketing" for tool in payload["tools"])


def test_plan_tool_request_returns_structured_plan():
    response = plan_tool_request("Create a high severity ticket for payment-service in production")

    assert response.route_hint == "tool_execution"
    assert response.tool_name == "ticketing"
    assert response.action == "create"
    assert response.target == "payment-service"
    assert response.arguments["severity"] == "high"
    assert response.arguments["environment"] == "production"


def test_plan_tool_request_maps_search_queries_to_document_search():
    response = plan_tool_request("Search docs for RAG architecture")

    assert response.tool_name == "document_search"
    assert response.action == "query"
    assert response.target == "RAG architecture"


def test_plan_tool_request_extracts_filename_for_document_search():
    response = plan_tool_request("Search rag_overview.md for reranking")

    assert response.tool_name == "document_search"
    assert response.arguments["filename"] == "rag_overview.md"


def test_plan_tool_request_extracts_max_results_for_document_search():
    response = plan_tool_request("Search docs for RAG and show top 2 results")

    assert response.tool_name == "document_search"
    assert response.arguments["max_results"] == "2"
    assert response.target == "RAG"


def test_plan_tool_request_extracts_first_results_limit_for_document_search():
    response = plan_tool_request("Search docs for RAG and show first 3 results")

    assert response.tool_name == "document_search"
    assert response.arguments["max_results"] == "3"
    assert response.target == "RAG"


def test_plan_tool_request_extracts_limit_results_for_document_search():
    response = plan_tool_request("Search rag_overview.md for reranking limit to 1")

    assert response.tool_name == "document_search"
    assert response.arguments["filename"] == "rag_overview.md"
    assert response.arguments["max_results"] == "1"
    assert response.target == "reranking"


def test_plan_tool_request_maps_status_queries_to_system_status():
    response = plan_tool_request("Check system status")

    assert response.tool_name == "system_status"
    assert response.action == "query"
    assert response.target == "system status"


def test_plan_tool_request_extracts_environment_for_system_status():
    response = plan_tool_request("Check system status for payment-service in production")

    assert response.tool_name == "system_status"
    assert response.action == "query"
    assert response.target == "payment-service"
    assert response.arguments["environment"] == "production"


def test_plan_tool_request_maps_ticket_status_queries_to_ticketing_query():
    response = plan_tool_request("Check ticket status for payment-service")

    assert response.tool_name == "ticketing"
    assert response.action == "query"
    assert response.target == "payment-service"


def test_plan_tool_request_maps_ticket_list_queries_to_ticketing_list():
    response = plan_tool_request("List open tickets")

    assert response.tool_name == "ticketing"
    assert response.action == "list"
    assert response.target == "tickets"
    assert response.arguments["status"] == "open"


def test_plan_tool_request_extracts_ticket_target_filter_for_list_queries():
    response = plan_tool_request("List open tickets for payment service")

    assert response.tool_name == "ticketing"
    assert response.action == "list"
    assert response.target == "tickets"
    assert response.arguments["status"] == "open"
    assert response.arguments["target_filter"] == "payment-service"


def test_plan_tool_request_extracts_combined_ticket_list_filters():
    response = plan_tool_request(
        "List high severity open tickets for payment service in production"
    )

    assert response.tool_name == "ticketing"
    assert response.action == "list"
    assert response.target == "tickets"
    assert response.arguments["status"] == "open"
    assert response.arguments["target_filter"] == "payment-service"
    assert response.arguments["severity_filter"] == "high"
    assert response.arguments["environment_filter"] == "production"


def test_plan_tool_request_extracts_max_results_for_ticket_list_queries():
    response = plan_tool_request("List open tickets for payment service and show top 2 results")

    assert response.tool_name == "ticketing"
    assert response.action == "list"
    assert response.target == "tickets"
    assert response.arguments["status"] == "open"
    assert response.arguments["target_filter"] == "payment-service"
    assert response.arguments["max_results"] == "2"


def test_plan_tool_request_extracts_ticket_id_for_close_requests():
    response = plan_tool_request("Close ticket TICKET-0007 for payment-service")

    assert response.tool_name == "ticketing"
    assert response.action == "close"
    assert response.target == "payment-service"
    assert response.arguments["ticket_id"] == "TICKET-0007"


def test_plan_tool_request_extracts_ticket_id_for_update_requests():
    response = plan_tool_request("Update ticket TICKET-0009 for checkout-api to high severity")

    assert response.tool_name == "ticketing"
    assert response.action == "update"
    assert response.target == "checkout-api"
    assert response.arguments["ticket_id"] == "TICKET-0009"
    assert response.arguments["severity"] == "high"


def test_plan_tool_request_maps_set_ticket_severity_to_update():
    response = plan_tool_request("Set ticket TICKET-0003 severity to medium")

    assert response.tool_name == "ticketing"
    assert response.action == "update"
    assert response.target == "ticket"
    assert response.arguments["ticket_id"] == "TICKET-0003"
    assert response.arguments["severity"] == "medium"


def test_plan_tool_request_maps_move_ticket_to_environment_update():
    response = plan_tool_request("Move ticket TICKET-0004 for payment-service to staging")

    assert response.tool_name == "ticketing"
    assert response.action == "update"
    assert response.target == "payment-service"
    assert response.arguments["ticket_id"] == "TICKET-0004"
    assert response.arguments["environment"] == "staging"


def test_plan_tool_request_extracts_ticket_status_update():
    response = plan_tool_request("Update ticket TICKET-0010 for payment-service status to closed")

    assert response.tool_name == "ticketing"
    assert response.action == "update"
    assert response.target == "payment-service"
    assert response.arguments["ticket_id"] == "TICKET-0010"
    assert response.arguments["status"] == "closed"


def test_plan_tool_request_uses_llm_planner_when_available(monkeypatch):
    monkeypatch.setattr(settings, "tool_planner_provider", "openai")
    monkeypatch.setattr(
        "app.services.agent.tool_service.generate_llm_tool_plan",
        lambda question, supported_tools: (
            "llm_openai",
            {
                "tool_name": "ticketing",
                "action": "create",
                "target": "payment-service",
                "arguments": {"severity": "high", "environment": "production"},
            },
        ),
    )

    response = plan_tool_request("Create a high severity ticket for payment-service in production")

    assert response.planning_mode == "llm_openai"
    assert response.tool_name == "ticketing"
    assert response.action == "create"
    assert response.target == "payment-service"
    assert response.arguments["severity"] == "high"
    assert response.arguments["environment"] == "production"


def test_plan_tool_request_falls_back_when_llm_plan_is_invalid(monkeypatch):
    monkeypatch.setattr(settings, "tool_planner_provider", "gemini")
    monkeypatch.setattr(
        "app.services.agent.tool_service.generate_llm_tool_plan",
        lambda question, supported_tools: (
            "llm_gemini",
            {
                "tool_name": "not_a_real_tool",
                "action": "create",
                "target": "payment-service",
                "arguments": {},
            },
        ),
    )

    response = plan_tool_request("Create a high severity ticket for payment-service in production")

    assert response.planning_mode == "heuristic_fallback_invalid_llm_plan"
    assert response.tool_name == "ticketing"
    assert response.action == "create"
    assert response.target == "payment-service"


def test_plan_tool_request_falls_back_when_llm_provider_is_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "tool_planner_provider", "openai")
    monkeypatch.setattr(
        "app.services.agent.tool_service.generate_llm_tool_plan",
        lambda question, supported_tools: ("heuristic_fallback_missing_openai_key", None),
    )

    response = plan_tool_request("Search docs for RAG architecture")

    assert response.planning_mode == "heuristic_fallback_missing_openai_key"
    assert response.tool_name == "document_search"
    assert response.action == "query"


def test_plan_tool_request_normalizes_llm_document_search_query_contract(monkeypatch):
    monkeypatch.setattr(settings, "tool_planner_provider", "gemini")
    monkeypatch.setattr(
        "app.services.agent.tool_service.generate_llm_tool_plan",
        lambda question, supported_tools: (
            "llm_gemini",
            {
                "tool_name": "document_search",
                "action": "query",
                "target": "docs",
                "arguments": {
                    "query": "payment-service outage",
                    "max_results": "2",
                },
            },
        ),
    )

    response = plan_tool_request("Search docs for payment-service outage and summarize top 2 results")

    assert response.planning_mode == "llm_gemini"
    assert response.tool_name == "document_search"
    assert response.action == "query"
    assert response.target == "payment-service outage"
    assert "query" not in response.arguments
    assert response.arguments["max_results"] == "2"


def test_query_tool_plan_endpoint_returns_plan():
    client = TestClient(app)
    response = client.post(
        "/api/query/tools/plan",
        json={
            "question": "Create a high severity ticket for payment-service in production",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_name"] == "ticketing"
    assert payload["action"] == "create"
    assert payload["target"] == "payment-service"
    assert payload["arguments"]["severity"] == "high"


def test_plan_clarification_uses_llm_planner_when_available(monkeypatch):
    monkeypatch.setattr(settings, "clarification_planner_provider", "gemini")
    monkeypatch.setattr(
        "app.services.agent.clarification_service.generate_llm_clarification_plan",
        lambda **kwargs: (
            "llm_gemini",
            {
                "missing_fields": ["target", "priority"],
                "follow_up_questions": [
                    "Which service should the agent act on?",
                    "What severity should the ticket use?",
                ],
                "clarification_summary": "The request needs more detail before execution.",
            },
        ),
    )

    response = plan_clarification("Please do that for production")

    assert response.planning_mode == "llm_gemini"
    assert response.missing_fields == ["target", "priority"]
    assert response.follow_up_questions


def test_plan_clarification_normalizes_llm_missing_fields_against_explicit_context(monkeypatch):
    monkeypatch.setattr(settings, "clarification_planner_provider", "gemini")
    monkeypatch.setattr(
        "app.services.agent.clarification_service.generate_llm_clarification_plan",
        lambda **kwargs: (
            "llm_gemini",
            {
                "missing_fields": ["environment", "action"],
                "follow_up_questions": [
                    "What specific action do you want to perform in production?",
                    "Which environment are you referring to?",
                ],
                "clarification_summary": "To proceed, I need the action and environment.",
            },
        ),
    )

    response = plan_clarification("Please do that for production")

    assert response.planning_mode == "llm_gemini"
    assert response.missing_fields == ["action"]
    assert response.follow_up_questions == ["What specific action do you want to perform in production?"]


def test_plan_clarification_converges_to_task_details_when_llm_only_repeats_present_fields(monkeypatch):
    monkeypatch.setattr(settings, "clarification_planner_provider", "gemini")
    monkeypatch.setattr(
        "app.services.agent.clarification_service.generate_llm_clarification_plan",
        lambda **kwargs: (
            "llm_gemini",
            {
                "missing_fields": ["environment"],
                "follow_up_questions": ["Which environment are you referring to?"],
                "clarification_summary": "I need the environment before proceeding.",
            },
        ),
    )

    response = plan_clarification("Restart payment-service in production")

    assert response.planning_mode == "llm_gemini"
    assert response.missing_fields == ["task_details"]
    assert response.follow_up_questions == ["What exact action should the agent perform?"]


def test_plan_search_miss_clarification_uses_llm_planner_when_available(monkeypatch):
    monkeypatch.setattr(settings, "clarification_planner_provider", "openai")
    monkeypatch.setattr(
        "app.services.agent.clarification_service.generate_llm_clarification_plan",
        lambda **kwargs: (
            "llm_openai",
            {
                "missing_fields": ["search_query_refinement", "execution_confirmation"],
                "follow_up_questions": [
                    "Should I refine the search phrase?",
                    "Do you want to continue without supporting documents?",
                ],
                "clarification_summary": "The workflow needs clarification before action can continue.",
            },
        ),
    )

    response = plan_search_miss_clarification(
        "payment-service outage",
        "create a high severity ticket for payment-service",
    )

    assert response.planning_mode == "llm_openai"
    assert response.missing_fields == ["search_query_refinement", "execution_confirmation"]
    assert response.follow_up_questions


def test_query_agent_endpoint_uses_llm_workflow_planner_for_non_regex_multistep_request(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "notes.md").write_text(
        "The payment-service outage requires a high severity response.",
        encoding="utf-8",
    )
    ticket_store_path = workspace_tmp_path / "tickets.json"

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)
    monkeypatch.setattr(settings, "workflow_planner_provider", "gemini")
    monkeypatch.setattr(settings, "tool_planner_provider", "gemini")
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.generate_llm_workflow_plan",
        lambda question: (
            "llm_gemini",
            {
                "workflow_kind": "search_then_ticket",
                "search_question": "Search docs for payment-service outage",
                "follow_up_question": "create a high severity ticket for payment-service",
            },
        ),
    )
    monkeypatch.setattr(
        "app.services.agent.tool_service.generate_llm_tool_plan",
        lambda question, supported_tools: (
            "llm_gemini",
            {
                "tool_name": "document_search"
                if "search docs" in question.lower()
                else "ticketing",
                "action": "query" if "search docs" in question.lower() else "create",
                "target": "payment-service outage"
                if "search docs" in question.lower()
                else "payment-service",
                "arguments": {"severity": "high"} if "ticket" in question.lower() else {},
            },
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Look up docs about payment-service outage, then create a high severity ticket for payment-service",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["step_count"] == 2
    assert payload["workflow_planning_mode"] == "llm_gemini"
    assert payload["tool_planning_mode"] == "llm_gemini"
    assert payload["tool_planning_modes"] == ["llm_gemini", "llm_gemini"]
    assert payload["clarification_planning_mode"] is None
    assert payload["tool_planner_call_count"] == 2
    assert payload["planner_call_count"] == 3
    assert payload["workflow_planning_latency_ms"] >= 0
    assert payload["tool_planning_latency_ms"] >= 0
    assert payload["clarification_planning_latency_ms"] == 0
    assert payload["planner_latency_ms_total"] == (
        payload["workflow_planning_latency_ms"]
        + payload["tool_planning_latency_ms"]
        + payload["clarification_planning_latency_ms"]
    )
    assert payload["llm_planner_layers"] == ["workflow", "tool"]
    assert payload["fallback_planner_layers"] == []
    assert payload["llm_tool_planner_steps"] == [1, 2]
    assert payload["fallback_tool_planner_steps"] == []
    assert payload["tool_chain"][0]["tool_plan"]["tool_name"] == "document_search"
    assert payload["tool_chain"][1]["tool_plan"]["tool_name"] == "ticketing"
    assert any(
        event["stage"] == "workflow_planning"
        and "search_then_ticket workflow via llm_gemini" in event["detail"]
        for event in payload["workflow_trace"]
    )


def test_query_agent_endpoint_falls_back_to_regex_multistep_when_llm_workflow_plan_is_invalid(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text(
        "RAG combines document retrieval with language model generation.",
        encoding="utf-8",
    )
    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr(settings, "workflow_planner_provider", "gemini")
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.generate_llm_workflow_plan",
        lambda question: ("llm_gemini", {"workflow_kind": "not_real", "search_question": "", "follow_up_question": ""}),
    )

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Search docs for RAG and summarize top 1 results",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["answer_source"] == "local_search_summary"
    assert payload["tool_plan"]["tool_name"] == "document_search"
    assert any(
        event["stage"] == "workflow_planning"
        and "search_then_summarize workflow via heuristic workflow matcher after invalid llm workflow plan"
        in event["detail"]
        for event in payload["workflow_trace"]
    )


def test_query_agent_endpoint_reports_clean_workflow_planner_fallback_reason(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text(
        "RAG combines document retrieval with language model generation.",
        encoding="utf-8",
    )
    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr(settings, "workflow_planner_provider", "gemini")
    monkeypatch.setattr(settings, "tool_planner_provider", "gemini")
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.generate_llm_workflow_plan",
        lambda question: ("heuristic_fallback_after_gemini_error", None),
    )
    monkeypatch.setattr(
        "app.services.agent.tool_service.generate_llm_tool_plan",
        lambda question, supported_tools: ("heuristic_fallback_after_gemini_error", None),
    )

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Look up docs about RAG, then summarize top 1 results",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert any(
        event["stage"] == "workflow_planning"
        and "search_then_summarize workflow via heuristic workflow matcher after gemini error"
        in event["detail"]
        for event in payload["workflow_trace"]
    )
    assert payload["workflow_planning_mode"] == "heuristic workflow matcher after gemini error"
    assert payload["tool_planning_mode"] == "heuristic_fallback_after_gemini_error"
    assert payload["tool_planning_modes"] == ["heuristic_fallback_after_gemini_error"]
    assert payload["tool_planner_call_count"] == 1
    assert payload["planner_call_count"] == 2
    assert payload["workflow_planning_latency_ms"] >= 0
    assert payload["tool_planning_latency_ms"] >= 0
    assert payload["clarification_planning_latency_ms"] == 0
    assert payload["planner_latency_ms_total"] == (
        payload["workflow_planning_latency_ms"]
        + payload["tool_planning_latency_ms"]
        + payload["clarification_planning_latency_ms"]
    )
    assert payload["llm_planner_layers"] == []
    assert payload["fallback_planner_layers"] == ["workflow", "tool"]
    assert payload["llm_tool_planner_steps"] == []
    assert payload["fallback_tool_planner_steps"] == [1]


def test_query_agent_endpoint_supports_then_style_multistep_without_llm_workflow_planner(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text(
        "RAG combines document retrieval with language model generation.",
        encoding="utf-8",
    )
    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Look up docs about RAG, then summarize top 1 results",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["answer_source"] == "local_search_summary"
    assert payload["workflow_planning_mode"] == "heuristic workflow matcher"
    assert payload["tool_planning_modes"] == ["heuristic_stub"]
    assert payload["tool_planner_call_count"] == 1
    assert payload["planner_call_count"] == 2
    assert payload["workflow_planning_latency_ms"] == 0
    assert payload["tool_planning_latency_ms"] >= 0
    assert payload["clarification_planning_latency_ms"] == 0
    assert payload["planner_latency_ms_total"] == payload["tool_planning_latency_ms"]
    assert payload["llm_planner_layers"] == []
    assert payload["fallback_planner_layers"] == ["tool"]
    assert payload["llm_tool_planner_steps"] == []
    assert payload["fallback_tool_planner_steps"] == [1]
    assert any(
        event["stage"] == "workflow_planning"
        and "search_then_summarize workflow via heuristic workflow matcher" in event["detail"]
        for event in payload["workflow_trace"]
    )


def test_parse_llm_workflow_plan_response_accepts_json_with_explanatory_wrapper():
    payload = _parse_llm_workflow_plan_response(
        'Here is the plan: {"workflow_kind":"search_then_summarize","search_question":"Look up docs about RAG","follow_up_question":"summarize top 1 results"}'
    )

    assert payload == {
        "workflow_kind": "search_then_summarize",
        "search_question": "Look up docs about RAG",
        "follow_up_question": "summarize top 1 results",
    }


def test_parse_llm_workflow_plan_response_accepts_status_then_ticket_kind():
    payload = _parse_llm_workflow_plan_response(
        '{"workflow_kind":"status_check_then_ticket","search_question":"Check system status for payment-service","follow_up_question":"create a high severity ticket for payment-service"}'
    )

    assert payload == {
        "workflow_kind": "status_then_ticket",
        "search_question": "Check system status for payment-service",
        "follow_up_question": "create a high severity ticket for payment-service",
    }


def test_parse_llm_workflow_plan_response_accepts_status_then_summarize_kind():
    payload = _parse_llm_workflow_plan_response(
        '{"workflow_kind":"status_then_summarize","search_question":"Check system status for payment-service","follow_up_question":"summarize the result"}'
    )

    assert payload == {
        "workflow_kind": "status_then_summarize",
        "search_question": "Check system status for payment-service",
        "follow_up_question": "summarize the result",
    }


def test_generate_llm_tool_plan_reuses_cached_result(monkeypatch):
    call_count = 0

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '{"tool_name":"document_search","action":"query","target":"RAG","arguments":{"max_results":"1"}}'
                                }
                            ]
                        }
                    }
                ]
            }

    def _fake_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return _FakeResponse()

    monkeypatch.setattr(settings, "tool_planner_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr("app.services.llm.tool_planner_service.httpx.post", _fake_post)

    supported_tools = {
        "document_search": {
            "supported_actions": ["query"],
            "description": "Search documents.",
        }
    }

    first_mode, first_plan = generate_llm_tool_plan("Look up docs about RAG", supported_tools)
    second_mode, second_plan = generate_llm_tool_plan("Look up docs about RAG", supported_tools)

    assert first_mode == "llm_gemini"
    assert second_mode == "llm_gemini"
    assert first_plan == second_plan
    assert call_count == 1


def test_generate_llm_clarification_plan_reuses_cached_result(monkeypatch):
    call_count = 0

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '{"missing_fields":["action"],"follow_up_questions":["What action should I take?"],"clarification_summary":"The request should be clarified before continuing."}'
                                }
                            ]
                        }
                    }
                ]
            }

    def _fake_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return _FakeResponse()

    monkeypatch.setattr(settings, "clarification_planner_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr("app.services.llm.clarification_planner_service.httpx.post", _fake_post)

    first_mode, first_plan = generate_llm_clarification_plan(
        mode="general",
        question="Please do that for production",
    )
    second_mode, second_plan = generate_llm_clarification_plan(
        mode="general",
        question="Please do that for production",
    )

    assert first_mode == "llm_gemini"
    assert second_mode == "llm_gemini"
    assert first_plan == second_plan
    assert call_count == 1


def test_generate_llm_workflow_plan_reuses_cached_result(monkeypatch):
    call_count = 0

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '{"workflow_kind":"search_then_summarize","search_question":"Look up docs about RAG","follow_up_question":"summarize top 1 results"}'
                                }
                            ],
                            "role": "model",
                        }
                    }
                ]
            }

    def _fake_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return _FakeResponse()

    monkeypatch.setattr(settings, "workflow_planner_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr("app.services.llm.workflow_planner_service.httpx.post", _fake_post)

    first_mode, first_plan = generate_llm_workflow_plan("Look up docs about RAG, then summarize top 1 results")
    second_mode, second_plan = generate_llm_workflow_plan("Look up docs about RAG, then summarize top 1 results")

    assert first_mode == "llm_gemini"
    assert second_mode == "llm_gemini"
    assert first_plan == second_plan
    assert call_count == 1


def test_parse_llm_workflow_plan_response_accepts_alias_keys_and_kind_names():
    payload = _parse_llm_workflow_plan_response(
        json.dumps(
            {
                "workflow_type": "search_then_summary",
                "search_step": "Look up docs about RAG",
                "summary_step": "summarize top 1 results",
            }
        )
    )

    assert payload == {
        "workflow_kind": "search_then_summarize",
        "search_question": "Look up docs about RAG",
        "follow_up_question": "summarize top 1 results",
    }


def test_extract_gemini_workflow_plan_text_collects_nested_candidate_text():
    payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "Here is the plan:"},
                        {
                            "functionCall": {
                                "name": "ignored",
                                "args": {"text": "ignore inner args text"},
                            }
                        },
                        {
                            "text": '{"workflow_kind":"search_then_summarize","search_question":"Look up docs about RAG","follow_up_question":"summarize top 1 results"}'
                        },
                    ]
                }
            }
        ]
    }

    extracted = _extract_gemini_workflow_plan_text(payload)

    assert "workflow_kind" in extracted
    assert "Look up docs about RAG" in extracted


def test_generate_gemini_workflow_plan_captures_debug_payload(
    workspace_tmp_path,
    monkeypatch,
):
    debug_path = workspace_tmp_path / "workflow_planner_debug.json"
    monkeypatch.setattr(settings, "workflow_planner_debug_capture", True)
    monkeypatch.setattr(
        "app.services.llm.workflow_planner_service.WORKFLOW_PLANNER_DEBUG_PATH",
        debug_path,
    )
    monkeypatch.setattr(settings, "gemini_workflow_planner_model", "gemini-test-model")
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": (
                                        '{"workflow_kind":"search_then_summarize",'
                                        '"search_question":"Look up docs about RAG",'
                                        '"follow_up_question":"summarize top 1 results"}'
                                    )
                                }
                            ]
                        }
                    }
                ]
            }

    monkeypatch.setattr(
        "app.services.llm.workflow_planner_service.httpx.post",
        lambda *args, **kwargs: _FakeResponse(),
    )

    payload = _generate_gemini_workflow_plan("Look up docs about RAG, then summarize top 1 results")

    assert payload == {
        "workflow_kind": "search_then_summarize",
        "search_question": "Look up docs about RAG",
        "follow_up_question": "summarize top 1 results",
    }
    assert debug_path.exists()
    debug_payload = json.loads(debug_path.read_text(encoding="utf-8"))
    assert debug_payload["provider"] == "gemini"
    assert debug_payload["status"] == "parsed_success"
    assert "workflow_kind" in debug_payload["raw_text"]


def test_plan_clarification_falls_back_when_provider_is_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "clarification_planner_provider", "gemini")
    monkeypatch.setattr(
        "app.services.agent.clarification_service.generate_llm_clarification_plan",
        lambda **kwargs: ("heuristic_fallback_missing_gemini_key", None),
    )

    response = plan_clarification("Please do that for production")

    assert response.planning_mode == "heuristic_fallback_missing_gemini_key"
    assert "target" in response.missing_fields


def test_query_agent_endpoint_returns_knowledge_workflow_result(
    workspace_tmp_path,
    monkeypatch,
):
    embedding_dir = workspace_tmp_path / "embeddings"
    embedding_dir.mkdir()

    monkeypatch.setattr(embedding_service, "EMBEDDING_DATA_DIR", embedding_dir)
    monkeypatch.setattr(settings, "chat_provider", "fallback")

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

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "filename": "sample.txt",
            "question": "What are rag systems?",
            "top_k": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["terminal_reason"] == "knowledge_answer_generated"
    assert payload["outcome_category"] == "completed"
    assert payload["is_recoverable"] is False
    assert payload["retry_state"] == "not_applicable"
    assert payload["recommended_recovery_action"] == "none"
    assert payload["available_recovery_actions"] == []
    assert payload["route"]["route_type"] == "knowledge_retrieval"
    assert len(payload["workflow_trace"]) >= 3
    assert payload["retrieval"]["filename"] == "sample.txt"
    assert payload["answer"]


def test_query_agent_endpoint_returns_tool_workflow_result(workspace_tmp_path, monkeypatch):
    ticket_store_path = workspace_tmp_path / "tickets.json"
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Create a ticket for the payment service outage",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["terminal_reason"] == "tool_execution_completed"
    assert payload["step_count"] == 1
    assert payload["started_at"]
    assert payload["completed_at"]
    assert payload["last_updated_at"] == payload["completed_at"]
    assert payload["route"]["route_type"] == "tool_execution"
    assert len(payload["workflow_trace"]) >= 3
    assert payload["tool_plan"]["tool_name"] == "ticketing"
    assert payload["tool_execution"]["execution_status"] == "completed"
    assert payload["tool_chain"][0]["step_id"] == "step_1"
    assert payload["tool_chain"][0]["step_index"] == 1
    assert payload["tool_chain"][0]["step_status"] == "completed"
    assert payload["tool_chain"][0]["started_at"]
    assert payload["tool_chain"][0]["completed_at"]
    assert any(
        event["stage"] == "tool_execution"
        and "local_adapter tool ticketing:create" in event["detail"]
        for event in payload["workflow_trace"]
    )


def test_query_agent_endpoint_clarifies_unsupported_direct_action_instead_of_creating_ticket():
    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Restart payment-service in production",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "clarification_required"
    assert payload["terminal_reason"] == "unsupported_action_clarification"
    assert payload["outcome_category"] == "clarification_required"
    assert payload["is_recoverable"] is True
    assert payload["retry_state"] == "not_applicable"
    assert payload["recommended_recovery_action"] == "resume_with_clarification"
    assert payload["available_recovery_actions"] == ["resume_with_clarification"]
    assert payload["recovery_action_details"] == {
        "resume_with_clarification": {
            "missing_fields": ["execution_confirmation", "fallback_action"],
        }
    }
    assert payload["tool_planning_mode"] == "guardrail_ticket_fallback"
    assert payload["tool_planning_modes"] == ["guardrail_ticket_fallback"]
    assert payload["tool_planner_call_count"] == 1
    assert payload["clarification_planning_mode"] == "guardrail_stub"
    assert payload["planner_call_count"] == 2
    assert payload["fallback_planner_layers"] == ["tool", "clarification"]
    assert payload["fallback_tool_planner_steps"] == [1]
    assert payload["step_count"] == 0
    assert payload["tool_execution"] is None
    assert payload["tool_plan"]["tool_name"] == "ticketing"
    assert payload["tool_plan"]["action"] == "create"
    assert payload["clarification_plan"]["planning_mode"] == "guardrail_stub"
    assert payload["clarification_plan"]["missing_fields"] == [
        "execution_confirmation",
        "fallback_action",
    ]
    assert any(
        event["stage"] == "clarification_planning"
        and "unsupported direct operational action" in event["detail"]
        for event in payload["workflow_trace"]
    )


def test_query_agent_endpoint_allows_explicit_ticket_creation_for_operational_issue(
    workspace_tmp_path,
    monkeypatch,
):
    ticket_store_path = workspace_tmp_path / "tickets.json"
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Create a ticket to restart payment-service in production",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["terminal_reason"] == "tool_execution_completed"
    assert payload["tool_execution"]["tool_name"] == "ticketing"
    assert payload["tool_execution"]["action"] == "create"


def test_query_agent_endpoint_allows_search_requests_that_mention_operational_verbs():
    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Search docs for how to restart payment-service in production",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"]["route_type"] == "tool_execution"
    assert payload["tool_plan"]["tool_name"] == "document_search"


def test_query_agent_endpoint_returns_document_search_workflow_with_filename_hint():
    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Search rag_overview.md for reranking",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"]["route_type"] == "tool_execution"
    assert payload["tool_plan"]["tool_name"] == "document_search"
    assert payload["tool_plan"]["arguments"]["filename"] == "rag_overview.md"
    assert payload["tool_plan"]["target"] == "reranking"


def test_query_agent_endpoint_supports_search_then_ticket_multistep_workflow(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "notes.md").write_text(
        "The payment-service outage requires a high severity response.",
        encoding="utf-8",
    )
    ticket_store_path = workspace_tmp_path / "tickets.json"

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Search docs for payment-service outage and create a high severity ticket for payment-service",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["terminal_reason"] == "tool_execution_completed"
    assert payload["step_count"] == 2
    assert payload["started_at"]
    assert payload["completed_at"]
    assert payload["last_updated_at"] == payload["completed_at"]
    assert payload["route"]["route_type"] == "tool_execution"
    assert len(payload["tool_chain"]) == 2
    assert payload["tool_chain"][0]["step_id"] == "step_1"
    assert payload["tool_chain"][0]["step_index"] == 1
    assert payload["tool_chain"][1]["step_id"] == "step_2"
    assert payload["tool_chain"][1]["step_index"] == 2
    assert payload["tool_chain"][1]["step_status"] == "completed"
    assert payload["tool_chain"][1]["started_at"]
    assert payload["tool_chain"][1]["completed_at"]
    assert payload["tool_chain"][0]["tool_plan"]["tool_name"] == "document_search"
    assert payload["tool_chain"][1]["tool_plan"]["tool_name"] == "ticketing"
    assert payload["tool_chain"][1]["tool_plan"]["arguments"]["supporting_query"] == "payment-service outage"
    assert "notes.md" in payload["tool_chain"][1]["tool_plan"]["arguments"]["supporting_documents"]
    assert payload["tool_chain"][1]["tool_execution"]["output"]["ticket_id"].startswith("TICKET-")
    assert payload["tool_chain"][1]["tool_execution"]["output"]["supporting_query"] == "payment-service outage"
    assert "notes.md" in payload["tool_chain"][1]["tool_execution"]["output"]["supporting_documents"]
    assert "supporting_summary" in payload["tool_chain"][1]["tool_execution"]["output"]
    assert "payment-service outage" in payload["tool_chain"][1]["tool_execution"]["output"]["supporting_summary"]
    assert sum(1 for event in payload["workflow_trace"] if event["stage"] == "tool_execution") == 2
    assert any(event["stage"] == "tool_context" for event in payload["workflow_trace"])


def test_query_agent_endpoint_supports_search_then_ticket_update_workflow(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "notes.md").write_text(
        "The payment-service outage requires a high severity response.",
        encoding="utf-8",
    )
    ticket_store_path = workspace_tmp_path / "tickets.json"
    ticket_store_path.write_text(
        json.dumps(
            [
                {
                    "ticket_id": "TICKET-0001",
                    "target": "payment-service",
                    "status": "open",
                    "severity": "high",
                    "environment": "production",
                    "created_at": "2026-03-16T00:00:00+00:00",
                    "updated_at": "2026-03-16T00:00:00+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": (
                "Search docs for payment-service outage and update ticket TICKET-0001 "
                "for payment-service status to closed"
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["terminal_reason"] == "tool_execution_completed"
    assert payload["step_count"] == 2
    assert payload["workflow_trace"][1]["stage"] == "workflow_planning"
    assert "search_then_ticket workflow" in payload["workflow_trace"][1]["detail"]
    assert payload["tool_chain"][0]["tool_plan"]["tool_name"] == "document_search"
    assert payload["tool_chain"][1]["tool_plan"]["tool_name"] == "ticketing"
    assert payload["tool_chain"][1]["tool_plan"]["action"] == "update"
    assert payload["tool_chain"][1]["tool_plan"]["target"] == "payment-service"
    assert payload["tool_chain"][1]["tool_plan"]["arguments"]["ticket_id"] == "TICKET-0001"
    assert payload["tool_chain"][1]["tool_plan"]["arguments"]["status"] == "closed"
    assert payload["tool_chain"][1]["tool_plan"]["arguments"]["supporting_query"] == "payment-service outage"
    assert "notes.md" in payload["tool_chain"][1]["tool_plan"]["arguments"]["supporting_documents"]
    assert payload["tool_chain"][1]["tool_execution"]["output"]["ticket_id"] == "TICKET-0001"
    assert payload["tool_chain"][1]["tool_execution"]["output"]["status"] == "closed"
    assert payload["tool_chain"][1]["tool_execution"]["output"]["supporting_query"] == "payment-service outage"
    assert "notes.md" in payload["tool_chain"][1]["tool_execution"]["output"]["supporting_documents"]
    assert "payment-service outage" in payload["tool_chain"][1]["tool_execution"]["output"]["supporting_summary"]
    assert any(event["stage"] == "tool_context" for event in payload["workflow_trace"])


def test_query_agent_endpoint_supports_status_then_ticket_multistep_workflow(
    workspace_tmp_path,
    monkeypatch,
):
    ticket_store_path = workspace_tmp_path / "tickets.json"
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Check system status for payment-service and create a high severity ticket for payment-service",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["terminal_reason"] == "tool_execution_completed"
    assert payload["step_count"] == 2
    assert payload["tool_planning_modes"] == [
        payload["tool_chain"][0]["tool_plan"]["planning_mode"],
        payload["tool_chain"][1]["tool_plan"]["planning_mode"],
    ]
    assert payload["tool_planner_call_count"] == 2
    assert payload["planner_call_count"] == 3
    assert payload["llm_tool_planner_steps"] == [
        index
        for index, mode in enumerate(payload["tool_planning_modes"], start=1)
        if mode.startswith("llm_")
    ]
    assert payload["fallback_tool_planner_steps"] == [
        index
        for index, mode in enumerate(payload["tool_planning_modes"], start=1)
        if not mode.startswith("llm_")
    ]
    assert payload["workflow_trace"][1]["stage"] == "workflow_planning"
    assert "status_then_ticket workflow" in payload["workflow_trace"][1]["detail"]
    assert payload["tool_chain"][0]["tool_plan"]["tool_name"] == "system_status"
    assert payload["tool_chain"][1]["tool_plan"]["tool_name"] == "ticketing"
    assert payload["tool_chain"][1]["tool_plan"]["arguments"]["supporting_status"] == "ok"
    assert payload["tool_chain"][1]["tool_plan"]["arguments"]["supporting_status_target"] == "payment-service"
    assert payload["tool_chain"][1]["tool_execution"]["output"]["supporting_status"] == "ok"
    assert payload["tool_chain"][1]["tool_execution"]["output"]["supporting_status_target"] == "payment-service"
    assert "System status snapshot for payment-service reported status ok" in (
        payload["tool_chain"][1]["tool_execution"]["output"]["supporting_summary"]
    )
    assert any(event["stage"] == "tool_context" for event in payload["workflow_trace"])


def test_query_agent_endpoint_supports_status_then_summarize_workflow():
    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Check system status for payment-service and summarize the result",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["terminal_reason"] == "status_summary_completed"
    assert payload["step_count"] == 1
    assert payload["answer_source"] == "local_status_summary"
    assert payload["chat_provider"] == "local"
    assert payload["chat_model"] == "local-heuristic-summary"
    assert payload["tool_plan"]["tool_name"] == "system_status"
    assert payload["tool_execution"]["tool_name"] == "system_status"
    assert "System status for payment-service is ok in development." in payload["answer"]
    assert "Current configuration: chat provider is gemini" in payload["answer"]
    assert any(
        event["stage"] == "status_summary"
        and "system status results" in event["detail"]
        for event in payload["workflow_trace"]
    )


def test_query_agent_endpoint_supports_environment_aware_status_then_summarize_workflow():
    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Check system status for payment-service in production and summarize the result",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["terminal_reason"] == "status_summary_completed"
    assert payload["tool_plan"]["tool_name"] == "system_status"
    assert payload["tool_plan"]["arguments"]["environment"] == "production"
    assert payload["tool_execution"]["output"]["requested_environment"] == "production"
    assert "requested for production" in payload["answer"]
    assert "in development" in payload["answer"]


def test_query_agent_endpoint_supports_status_then_ticket_close_workflow(
    workspace_tmp_path,
    monkeypatch,
):
    ticket_store_path = workspace_tmp_path / "tickets.json"
    ticket_store_path.write_text(
        json.dumps(
            [
                {
                    "ticket_id": "TICKET-0001",
                    "target": "payment-service",
                    "status": "open",
                    "severity": "high",
                    "environment": "production",
                    "created_at": "2026-03-16T00:00:00+00:00",
                    "updated_at": "2026-03-16T00:00:00+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": (
                "Check system status for payment-service and close ticket TICKET-0001 "
                "for payment-service"
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["terminal_reason"] == "tool_execution_completed"
    assert payload["step_count"] == 2
    assert payload["workflow_trace"][1]["stage"] == "workflow_planning"
    assert "status_then_ticket workflow" in payload["workflow_trace"][1]["detail"]
    assert payload["tool_chain"][0]["tool_plan"]["tool_name"] == "system_status"
    assert payload["tool_chain"][1]["tool_plan"]["tool_name"] == "ticketing"
    assert payload["tool_chain"][1]["tool_plan"]["action"] == "close"
    assert payload["tool_chain"][1]["tool_plan"]["arguments"]["ticket_id"] == "TICKET-0001"
    assert payload["tool_chain"][1]["tool_plan"]["arguments"]["supporting_status"] == "ok"
    assert payload["tool_chain"][1]["tool_execution"]["output"]["ticket_id"] == "TICKET-0001"
    assert payload["tool_chain"][1]["tool_execution"]["output"]["status"] == "closed"
    assert payload["tool_chain"][1]["tool_execution"]["output"]["supporting_status"] == "ok"
    assert payload["tool_chain"][1]["tool_execution"]["output"]["supporting_status_target"] == "payment-service"
    assert "System status snapshot for payment-service reported status ok" in (
        payload["tool_chain"][1]["tool_execution"]["output"]["supporting_summary"]
    )
    assert any(event["stage"] == "tool_context" for event in payload["workflow_trace"])


def test_query_agent_endpoint_stops_multistep_ticket_creation_when_search_misses(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "notes.md").write_text(
        "This file only mentions deployment workflows.",
        encoding="utf-8",
    )
    ticket_store_path = workspace_tmp_path / "tickets.json"

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Search docs for payment-service outage and create a high severity ticket for payment-service",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "clarification_required"
    assert payload["terminal_reason"] == "search_miss_clarification"
    assert payload["step_count"] == 1
    assert payload["started_at"]
    assert payload["completed_at"] is None
    assert payload["last_updated_at"]
    assert payload["route"]["route_type"] == "tool_execution"
    assert len(payload["tool_chain"]) == 1
    assert payload["tool_chain"][0]["step_id"] == "step_1"
    assert payload["tool_chain"][0]["step_index"] == 1
    assert payload["tool_chain"][0]["step_status"] == "completed"
    assert payload["tool_chain"][0]["tool_plan"]["tool_name"] == "document_search"
    assert payload["tool_execution"]["tool_name"] == "document_search"
    assert payload["tool_execution"]["output"]["matched_count"] == "0"
    assert payload["workflow_planning_latency_ms"] == 0
    assert payload["tool_planning_latency_ms"] >= 0
    assert payload["clarification_planning_latency_ms"] >= 0
    assert payload["planner_latency_ms_total"] == (
        payload["workflow_planning_latency_ms"]
        + payload["tool_planning_latency_ms"]
        + payload["clarification_planning_latency_ms"]
    )
    assert payload["clarification_message"]
    assert "search_query_refinement" in payload["clarification_plan"]["missing_fields"]
    assert "execution_confirmation" in payload["clarification_plan"]["missing_fields"]
    assert any(
        "different phrase or document set" in question
        for question in payload["clarification_plan"]["follow_up_questions"]
    )
    assert any(
        event["stage"] == "clarification_planning"
        and "Search produced no supporting documents" in event["detail"]
        for event in payload["workflow_trace"]
    )
    assert "before the ticket step" in payload["workflow_trace"][-1]["detail"]
    assert "before continuing to the ticket step" in payload["clarification_message"]


def test_query_agent_endpoint_supports_capped_document_search_workflow(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text("RAG appears here first and most clearly.", encoding="utf-8")
    (raw_dir / "notes.txt").write_text("RAG is mentioned in this note.", encoding="utf-8")
    (raw_dir / "summary.md").write_text("This summary also mentions RAG in passing.", encoding="utf-8")

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Search docs for RAG and show top 2 results",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["route"]["route_type"] == "tool_execution"
    assert payload["tool_plan"]["tool_name"] == "document_search"
    assert payload["tool_plan"]["arguments"]["max_results"] == "2"
    assert payload["tool_execution"]["output"]["max_results"] == "2"
    assert payload["tool_execution"]["output"]["returned_count"] == "2"
    assert len(payload["tool_execution"]["output"]["matched_documents"].split(", ")) == 2
    assert len(payload["tool_chain"]) == 1
    assert payload["tool_chain"][0]["tool_plan"]["tool_name"] == "document_search"


def test_query_agent_endpoint_supports_filename_scoped_limited_document_search(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text(
        "Reranking improves retrieval quality. Reranking also helps precision.",
        encoding="utf-8",
    )
    (raw_dir / "notes.md").write_text(
        "Reranking appears here too, but this should be filtered out.",
        encoding="utf-8",
    )

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Search rag_overview.md for reranking limit to 1",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["tool_plan"]["tool_name"] == "document_search"
    assert payload["tool_plan"]["arguments"]["filename"] == "rag_overview.md"
    assert payload["tool_plan"]["arguments"]["max_results"] == "1"
    assert payload["tool_execution"]["output"]["filename_filter"] == "rag_overview.md"
    assert payload["tool_execution"]["output"]["max_results"] == "1"
    assert payload["tool_execution"]["output"]["returned_count"] == "1"
    assert payload["tool_execution"]["output"]["matched_documents"] == "rag_overview.md"


def test_query_agent_endpoint_supports_search_then_summarize_workflow(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text(
        "# Retrieval-Augmented Generation Overview\n"
        "## What RAG Means\n"
        "RAG combines document retrieval with language model generation.",
        encoding="utf-8",
    )
    (raw_dir / "notes.txt").write_text(
        "RAG improves factual grounding and retrieval quality.",
        encoding="utf-8",
    )

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Search docs for RAG and summarize top 2 results",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["route"]["route_type"] == "tool_execution"
    assert payload["tool_plan"]["tool_name"] == "document_search"
    assert payload["tool_plan"]["arguments"]["max_results"] == "2"
    assert payload["answer_source"] == "local_search_summary"
    assert payload["chat_provider"] == "local"
    assert "I found 2 matching document(s)" in payload["answer"]
    assert "The strongest supporting document is" in payload["answer"]
    assert "Key evidence from rag_overview.md:" in payload["answer"]
    assert "Additional support from notes.txt:" in payload["answer"]
    assert "## What RAG Means" not in payload["answer"]
    assert "term coverage" not in payload["answer"]
    assert any(event["stage"] == "search_summary" for event in payload["workflow_trace"])
    assert len(payload["tool_chain"]) == 1


def test_query_agent_endpoint_avoids_extra_llm_tool_planner_call_for_summary_limit(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text(
        "RAG combines document retrieval with language model generation.",
        encoding="utf-8",
    )
    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr(settings, "tool_planner_provider", "gemini")

    planned_questions: list[str] = []

    def _fake_generate_llm_tool_plan(question, supported_tools):
        del supported_tools
        planned_questions.append(question)
        return (
            "llm_gemini",
            {
                "tool_name": "document_search",
                "action": "query",
                "target": "RAG",
                "arguments": {},
            },
        )

    monkeypatch.setattr(
        "app.services.agent.tool_service.generate_llm_tool_plan",
        _fake_generate_llm_tool_plan,
    )

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Search docs for RAG and summarize top 2 results",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["tool_plan"]["arguments"]["max_results"] == "2"
    assert planned_questions == ["Search docs for RAG"]


def test_query_agent_endpoint_stops_search_then_summarize_when_search_misses(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "notes.md").write_text(
        "This file only mentions deployment workflows.",
        encoding="utf-8",
    )

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Search docs for payment-service outage and summarize top 2 results",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "clarification_required"
    assert payload["terminal_reason"] == "search_summary_miss_clarification"
    assert payload["route"]["route_type"] == "tool_execution"
    assert payload["tool_execution"]["tool_name"] == "document_search"
    assert payload["tool_execution"]["output"]["matched_count"] == "0"
    assert "generating a summary" in payload["clarification_message"]
    assert "search_query_refinement" in payload["clarification_plan"]["missing_fields"]
    assert "document_scope" in payload["clarification_plan"]["missing_fields"]
    assert any(event["stage"] == "clarification_planning" for event in payload["workflow_trace"])


def test_query_agent_endpoint_supports_filename_scoped_search_summary(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text(
        "RAG combines retrieval with language model generation.\n\n"
        "## Retrieval and Reranking\n\n"
        "The first retrieval stage usually returns candidate chunks with vector similarity scores. "
        "Many production systems then apply a reranker to reorder the candidates. "
        "Reranking is useful when relevant chunks are present but not ranked highly enough.",
        encoding="utf-8",
    )
    (raw_dir / "notes.txt").write_text(
        "This file mentions retrieval but not reranking.",
        encoding="utf-8",
    )

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Search rag_overview.md for reranking and summarize top 1 results",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["tool_plan"]["arguments"]["filename"] == "rag_overview.md"
    assert payload["tool_plan"]["arguments"]["max_results"] == "1"
    assert payload["tool_execution"]["output"]["filename_filter"] == "rag_overview.md"
    assert payload["tool_execution"]["output"]["returned_count"] == "1"
    assert "I searched 'rag_overview.md' for 'reranking'" in payload["answer"]
    assert "The strongest supporting document is rag_overview.md." in payload["answer"]
    assert (
        "Key evidence from rag_overview.md: Reranking is useful when relevant chunks are present but not ranked highly enough."
        in payload["answer"]
    )
    assert "Key evidence from rag_overview.md: Reranking The first" not in payload["answer"]
    assert "Returned documents:" not in payload["answer"]


def test_query_agent_endpoint_returns_clarification_result():
    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Please do that for production",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "clarification_required"
    assert payload["terminal_reason"] == "clarification_requested"
    assert payload["step_count"] == 0
    assert payload["started_at"]
    assert payload["completed_at"] is None
    assert payload["last_updated_at"]
    assert payload["route"]["route_type"] == "clarification_needed"
    assert len(payload["workflow_trace"]) >= 2
    assert payload["clarification_message"]
    assert "missing_fields" in payload["clarification_plan"]
    assert payload["clarification_plan"]["follow_up_questions"]


def test_query_agent_endpoint_returns_structured_failure_for_knowledge_errors(
    monkeypatch,
):
    def raise_retrieval_failure(*args, **kwargs):
        raise RuntimeError("simulated retrieval failure")

    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.run_query",
        raise_retrieval_failure,
    )

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "What is RAG?",
            "filename": "rag_overview.md",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "failed"
    assert payload["terminal_reason"] == "knowledge_retrieval_failed"
    assert payload["outcome_category"] == "recoverable_failure"
    assert payload["is_recoverable"] is True
    assert payload["retry_state"] == "retry_available"
    assert payload["recommended_recovery_action"] == "retry"
    assert payload["available_recovery_actions"] == ["retry"]
    assert payload["recovery_action_details"] == {
        "retry": {
            "retries_from_start": True,
        }
    }
    assert payload["failure_stage"] == "retrieval"
    assert "simulated retrieval failure" in payload["failure_message"]
    assert payload["step_count"] == 0
    assert payload["started_at"]
    assert payload["completed_at"]
    assert payload["last_updated_at"] == payload["completed_at"]
    assert any(
        event["stage"] == "retrieval" and event["status"] == "failed"
        for event in payload["workflow_trace"]
    )


def test_query_agent_endpoint_returns_structured_failure_for_single_tool_errors(
    monkeypatch,
):
    attempt_counter = {"count": 0}

    def raise_tool_failure(*args, **kwargs):
        attempt_counter["count"] += 1
        raise RuntimeError("simulated tool failure")

    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.execute_tool_request",
        raise_tool_failure,
    )

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Create a ticket for the payment service outage",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "failed"
    assert payload["terminal_reason"] == "tool_execution_failed"
    assert payload["outcome_category"] == "recoverable_failure"
    assert payload["is_recoverable"] is True
    assert payload["retry_state"] == "retry_exhausted"
    assert payload["recommended_recovery_action"] == "manual_retrigger"
    assert payload["available_recovery_actions"] == ["manual_retrigger"]
    assert payload["recovery_action_details"] == {
        "manual_retrigger": {
            "restarts_workflow": True,
        }
    }
    assert payload["retry_count"] == 1
    assert payload["retried_step_indices"] == [1]
    assert payload["failure_stage"] == "tool_execution"
    assert "simulated tool failure" in payload["failure_message"]
    assert payload["step_count"] == 1
    assert payload["tool_plan"]["tool_name"] == "ticketing"
    assert payload["tool_execution"] is None
    assert payload["tool_chain"][0]["step_status"] == "failed"
    assert payload["tool_chain"][0]["attempt_count"] == 2
    assert payload["tool_chain"][0]["retried"] is True
    assert payload["tool_chain"][0]["tool_plan"]["tool_name"] == "ticketing"
    assert payload["tool_chain"][0]["tool_execution"] is None
    assert "simulated tool failure" in payload["tool_chain"][0]["failure_message"]
    assert attempt_counter["count"] == 2
    assert any(
        event["stage"] == "tool_execution" and event["status"] == "failed"
        for event in payload["workflow_trace"]
    )
    assert any(event["stage"] == "retry" for event in payload["workflow_trace"])


def test_query_agent_endpoint_preserves_completed_steps_before_multistep_failure(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "notes.md").write_text(
        "The payment-service outage requires a high severity response.",
        encoding="utf-8",
    )
    ticket_store_path = workspace_tmp_path / "tickets.json"

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    real_execute_tool_request = execute_tool_request

    attempt_counter = {"count": 0}

    def fail_ticket_step(request):
        if request.tool_name == "ticketing":
            attempt_counter["count"] += 1
            raise RuntimeError("simulated ticket failure")
        return real_execute_tool_request(request)

    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.execute_tool_request",
        fail_ticket_step,
    )

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Search docs for payment-service outage and create a high severity ticket for payment-service",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "failed"
    assert payload["terminal_reason"] == "tool_execution_failed"
    assert payload["outcome_category"] == "recoverable_failure"
    assert payload["is_recoverable"] is True
    assert payload["retry_state"] == "retry_exhausted"
    assert payload["recommended_recovery_action"] == "resume_from_failed_step"
    assert payload["available_recovery_actions"] == [
        "resume_from_failed_step",
        "manual_retrigger",
    ]
    assert payload["recovery_action_details"] == {
        "resume_from_failed_step": {
            "workflow_kind": "search_then_ticket",
            "target_step_index": 2,
            "reused_step_indices": [1],
        },
        "manual_retrigger": {
            "restarts_workflow": True,
        },
    }
    assert payload["retry_count"] == 1
    assert payload["retried_step_indices"] == [2]
    assert payload["failure_stage"] == "tool_execution"
    assert "simulated ticket failure" in payload["failure_message"]
    assert payload["step_count"] == 2
    assert len(payload["tool_chain"]) == 2
    assert payload["tool_chain"][0]["step_status"] == "completed"
    assert payload["tool_chain"][0]["tool_plan"]["tool_name"] == "document_search"
    assert payload["tool_chain"][1]["step_status"] == "failed"
    assert payload["tool_chain"][1]["attempt_count"] == 2
    assert payload["tool_chain"][1]["retried"] is True
    assert payload["tool_chain"][1]["tool_plan"]["tool_name"] == "ticketing"
    assert payload["tool_chain"][1]["tool_execution"] is None
    assert "simulated ticket failure" in payload["tool_chain"][1]["failure_message"]
    assert payload["tool_plan"]["tool_name"] == "ticketing"
    assert payload["tool_execution"] is None
    failed_execution_events = [
        event for event in payload["workflow_trace"] if event["stage"] == "tool_execution"
    ]
    assert attempt_counter["count"] == 2
    assert any(event["status"] == "failed" for event in failed_execution_events)
    assert any(event["stage"] == "retry" for event in payload["workflow_trace"])


def test_query_agent_endpoint_retries_single_tool_execution_once_and_recovers(
    workspace_tmp_path,
    monkeypatch,
):
    ticket_store_path = workspace_tmp_path / "tickets.json"
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    real_execute_tool_request = execute_tool_request
    attempt_counter = {"count": 0}

    def flaky_tool_execution(request):
        if request.tool_name == "ticketing":
            attempt_counter["count"] += 1
            if attempt_counter["count"] == 1:
                raise RuntimeError("transient ticket failure")
        return real_execute_tool_request(request)

    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.execute_tool_request",
        flaky_tool_execution,
    )

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Create a ticket for the payment service outage",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["terminal_reason"] == "tool_execution_completed"
    assert payload["retry_count"] == 1
    assert payload["retried_step_indices"] == [1]
    assert payload["retry_state"] == "not_applicable"
    assert payload["tool_execution"]["execution_status"] == "completed"
    assert payload["tool_chain"][0]["step_status"] == "completed"
    assert payload["tool_chain"][0]["attempt_count"] == 2
    assert payload["tool_chain"][0]["retried"] is True
    assert attempt_counter["count"] == 2
    assert any(event["stage"] == "retry" for event in payload["workflow_trace"])


def test_query_agent_endpoint_supports_debug_fault_injection_for_retry_recovery(
    workspace_tmp_path,
    monkeypatch,
):
    ticket_store_path = workspace_tmp_path / "tickets.json"
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Create a ticket for the payment service outage",
            "debug_fault_injection": {
                "tool_execution_failures": [
                    {
                        "tool_name": "ticketing",
                        "action": "create",
                        "fail_count": 1,
                        "message": "debug injected transient failure",
                    }
                ]
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["terminal_reason"] == "tool_execution_completed"
    assert payload["retry_count"] == 1
    assert payload["retried_step_indices"] == [1]
    assert payload["retry_state"] == "not_applicable"
    assert payload["tool_chain"][0]["attempt_count"] == 2
    assert payload["tool_chain"][0]["retried"] is True
    assert any(event["stage"] == "fault_injection" for event in payload["workflow_trace"])
    assert any(event["stage"] == "retry" for event in payload["workflow_trace"])


def test_query_agent_endpoint_supports_debug_fault_injection_for_retry_failure():
    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Create a ticket for the payment service outage",
            "debug_fault_injection": {
                "tool_execution_failures": [
                    {
                        "tool_name": "ticketing",
                        "action": "create",
                        "fail_count": 2,
                        "message": "debug injected persistent failure",
                    }
                ]
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "failed"
    assert payload["terminal_reason"] == "tool_execution_failed"
    assert payload["retry_state"] == "retry_exhausted"
    assert payload["retry_count"] == 1
    assert payload["retried_step_indices"] == [1]
    assert payload["recommended_recovery_action"] == "manual_retrigger"
    assert payload["tool_chain"][0]["attempt_count"] == 2
    assert payload["tool_chain"][0]["retried"] is True
    assert "debug injected persistent failure" in payload["failure_message"]
    assert any(event["stage"] == "fault_injection" for event in payload["workflow_trace"])
    assert any(event["stage"] == "retry" for event in payload["workflow_trace"])


def test_resume_agent_endpoint_continues_search_then_summarize_workflow(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text(
        "Retrieval-augmented generation, or RAG, combines retrieval and generation.\n\n"
        "Reranking helps order the strongest candidate chunks.",
        encoding="utf-8",
    )
    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)

    client = TestClient(app)
    response = client.post(
        "/api/query/agent/resume",
        json={
            "original_question": "Search docs for payment-service outage and summarize top 2 results",
            "clarification_context": {
                "search_query_refinement": "RAG",
                "document_scope": "rag_overview.md",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["resume_source_type"] == "original_question"
    assert payload["resume_strategy"] == "search_then_summarize_resume"
    assert payload["applied_clarification_fields"] == [
        "document_scope",
        "search_query_refinement",
    ]
    assert payload["question_rewritten"] is True
    assert payload["overridden_plan_arguments"] == ["filename", "target"]
    assert payload["question"] == "Search rag_overview.md for RAG and summarize top 2 results"
    assert payload["tool_plan"]["arguments"]["filename"] == "rag_overview.md"
    assert payload["tool_plan"]["arguments"]["max_results"] == "2"
    assert payload["answer_source"] == "local_search_summary"
    assert payload["workflow_trace"][0]["stage"] == "workflow_resume"
    assert "search_then_summarize_resume" in payload["workflow_trace"][0]["detail"]
    assert any(event["stage"] == "search_summary" for event in payload["workflow_trace"])


def test_resume_agent_endpoint_continues_search_then_ticket_workflow(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text(
        "RAG reduces hallucinations and improves factual grounding.",
        encoding="utf-8",
    )
    ticket_store_path = workspace_tmp_path / "tickets.json"

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    client = TestClient(app)
    response = client.post(
        "/api/query/agent/resume",
        json={
            "original_question": "Search docs for payment-service outage and create a high severity ticket for payment-service",
            "clarification_context": {
                "search_query_refinement": "RAG",
                "environment": "production",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["resume_source_type"] == "original_question"
    assert payload["resume_strategy"] == "search_then_ticket_resume"
    assert payload["applied_clarification_fields"] == [
        "environment",
        "search_query_refinement",
    ]
    assert payload["question_rewritten"] is True
    assert payload["overridden_plan_arguments"] == ["environment", "target"]
    assert payload["question"] == (
        "Search docs for RAG and create a high severity ticket for payment-service in production"
    )
    assert payload["tool_chain"][-1]["tool_plan"]["tool_name"] == "ticketing"
    assert payload["tool_chain"][-1]["tool_execution"]["output"]["environment"] == "production"
    assert payload["workflow_trace"][0]["stage"] == "workflow_resume"
    assert any(event["stage"] == "resume_context" for event in payload["workflow_trace"])


def test_resume_agent_endpoint_applies_structured_ticket_overrides(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text(
        "RAG reduces hallucinations and improves factual grounding.",
        encoding="utf-8",
    )
    ticket_store_path = workspace_tmp_path / "tickets.json"

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    client = TestClient(app)
    response = client.post(
        "/api/query/agent/resume",
        json={
            "original_question": "Search docs for payment-service outage and create a high severity ticket for payment-service",
            "clarification_context": {
                "search_query_refinement": "RAG",
                "environment": "staging",
                "severity": "medium",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["resume_strategy"] == "search_then_ticket_resume"
    assert payload["resume_source_type"] == "original_question"
    assert payload["applied_clarification_fields"] == [
        "environment",
        "search_query_refinement",
        "severity",
    ]
    assert payload["question_rewritten"] is True
    assert payload["overridden_plan_arguments"] == ["environment", "severity", "target"]
    final_plan = payload["tool_chain"][-1]["tool_plan"]
    final_output = payload["tool_chain"][-1]["tool_execution"]["output"]
    assert final_plan["arguments"]["environment"] == "staging"
    assert final_plan["arguments"]["severity"] == "medium"
    assert final_output["environment"] == "staging"
    assert final_output["severity"] == "medium"


def test_resume_agent_endpoint_applies_structured_ticket_overrides_for_ticket_update(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text(
        "RAG reduces hallucinations and improves factual grounding.",
        encoding="utf-8",
    )
    ticket_store_path = workspace_tmp_path / "tickets.json"
    ticket_store_path.write_text(
        json.dumps(
            [
                {
                    "ticket_id": "TICKET-0001",
                    "target": "payment-service",
                    "status": "open",
                    "severity": "high",
                    "environment": "production",
                    "created_at": "2026-03-16T00:00:00+00:00",
                    "updated_at": "2026-03-16T00:00:00+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    client = TestClient(app)
    response = client.post(
        "/api/query/agent/resume",
        json={
            "original_question": (
                "Search docs for payment-service outage and update ticket TICKET-0001 "
                "for payment-service status to open"
            ),
            "clarification_context": {
                "search_query_refinement": "RAG",
                "status": "closed",
                "environment": "staging",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["resume_strategy"] == "search_then_ticket_resume"
    assert payload["resume_source_type"] == "original_question"
    assert payload["applied_clarification_fields"] == [
        "environment",
        "search_query_refinement",
        "status",
    ]
    assert payload["question_rewritten"] is True
    assert payload["overridden_plan_arguments"] == ["environment", "status", "target"]
    final_plan = payload["tool_chain"][-1]["tool_plan"]
    final_output = payload["tool_chain"][-1]["tool_execution"]["output"]
    assert final_plan["action"] == "update"
    assert final_plan["arguments"]["ticket_id"] == "TICKET-0001"
    assert final_plan["arguments"]["status"] == "closed"
    assert final_plan["arguments"]["environment"] == "staging"
    assert final_plan["target"] == "payment-service"
    assert "service" not in final_plan["arguments"]
    assert final_output["ticket_id"] == "TICKET-0001"
    assert final_output["status"] == "closed"
    assert final_output["environment"] == "staging"
    assert final_output["supporting_query"] == "RAG"


def test_resume_agent_endpoint_can_continue_ticket_workflow_after_search_miss_when_confirmed(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "notes.txt").write_text(
        "This file only mentions deployment workflows.",
        encoding="utf-8",
    )
    ticket_store_path = workspace_tmp_path / "tickets.json"

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    client = TestClient(app)
    response = client.post(
        "/api/query/agent/resume",
        json={
            "original_question": "Search docs for payment-service outage and create a high severity ticket for payment-service",
            "clarification_context": {
                "execution_confirmation": "yes",
                "environment": "production",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["resume_source_type"] == "original_question"
    assert payload["resume_strategy"] == "search_then_ticket_resume"
    assert payload["applied_clarification_fields"] == [
        "environment",
        "execution_confirmation",
    ]
    assert payload["question_rewritten"] is True
    assert payload["overridden_plan_arguments"] == ["environment"]
    assert payload["tool_chain"][0]["tool_execution"]["output"]["matched_count"] == "0"
    assert payload["tool_chain"][-1]["tool_plan"]["tool_name"] == "ticketing"
    assert payload["tool_chain"][-1]["tool_execution"]["output"]["environment"] == "production"
    assert any(
        "execution continued" in event["detail"]
        for event in payload["workflow_trace"]
        if event["stage"] == "resume_context"
    )


def test_resume_agent_endpoint_continues_status_then_ticket_workflow(
    workspace_tmp_path,
    monkeypatch,
):
    ticket_store_path = workspace_tmp_path / "tickets.json"
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    client = TestClient(app)
    response = client.post(
        "/api/query/agent/resume",
        json={
            "original_question": (
                "Check system status for payment-service and create a high severity ticket "
                "for payment-service"
            ),
            "clarification_context": {
                "environment": "production",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["resume_source_type"] == "original_question"
    assert payload["resume_strategy"] == "status_then_ticket_resume"
    assert payload["applied_clarification_fields"] == ["environment"]
    assert payload["question_rewritten"] is True
    assert payload["overridden_plan_arguments"] == ["environment"]
    assert payload["question"] == (
        "Check system status for payment-service and create a high severity ticket "
        "for payment-service in production"
    )
    assert payload["tool_chain"][0]["tool_plan"]["tool_name"] == "system_status"
    assert payload["tool_chain"][-1]["tool_plan"]["tool_name"] == "ticketing"
    assert payload["tool_chain"][-1]["tool_execution"]["output"]["environment"] == "production"
    assert payload["workflow_trace"][0]["stage"] == "workflow_resume"
    assert "status_then_ticket_resume" in payload["workflow_trace"][0]["detail"]


def test_resume_agent_endpoint_continues_status_then_summarize_workflow():
    client = TestClient(app)
    response = client.post(
        "/api/query/agent/resume",
        json={
            "original_question": "Check system status for payment-service and summarize the result",
            "clarification_context": {
                "environment": "production",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "completed"
    assert payload["resume_source_type"] == "original_question"
    assert payload["resume_strategy"] == "status_then_summarize_resume"
    assert payload["applied_clarification_fields"] == ["environment"]
    assert payload["question_rewritten"] is False
    assert payload["overridden_plan_arguments"] == ["environment"]
    assert payload["answer_source"] == "local_status_summary"
    assert payload["workflow_trace"][0]["stage"] == "workflow_resume"
    assert "status_then_summarize_resume" in payload["workflow_trace"][0]["detail"]


def test_query_agent_endpoint_persists_workflow_run_and_supports_lookup(
    workspace_tmp_path,
    monkeypatch,
):
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"

    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Check system status",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"]
    assert payload["resumed_from_question"] is None

    lookup_response = client.get(f"/api/query/agent/runs/{payload['run_id']}")

    assert lookup_response.status_code == 200
    lookup_payload = lookup_response.json()
    assert lookup_payload["run_id"] == payload["run_id"]
    assert lookup_payload["question"] == "Check system status"
    assert lookup_payload["workflow_status"] == "completed"
    assert lookup_payload["terminal_reason"] == "tool_execution_completed"
    assert lookup_payload["started_at"]
    assert lookup_payload["completed_at"]
    assert lookup_payload["last_updated_at"] == lookup_payload["completed_at"]
    assert lookup_payload["tool_plan"]["tool_name"] == "system_status"
    assert workflow_run_store_path.exists()
    persisted_runs = json.loads(workflow_run_store_path.read_text(encoding="utf-8"))
    assert len(persisted_runs) == 1


def test_resume_agent_endpoint_persists_resumed_workflow_run_and_supports_lookup(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text(
        "Retrieval-augmented generation, or RAG, combines retrieval and generation.",
        encoding="utf-8",
    )
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )

    client = TestClient(app)
    response = client.post(
        "/api/query/agent/resume",
        json={
            "original_question": "Search docs for payment-service outage and summarize top 2 results",
            "clarification_context": {
                "search_query_refinement": "RAG",
                "document_scope": "rag_overview.md",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"]
    assert (
        payload["resumed_from_question"]
        == "Search docs for payment-service outage and summarize top 2 results"
    )
    assert payload["source_run_id"] is None
    assert payload["resume_source_type"] == "original_question"
    assert payload["resume_strategy"] == "search_then_summarize_resume"
    assert payload["applied_clarification_fields"] == [
        "document_scope",
        "search_query_refinement",
    ]
    assert payload["question_rewritten"] is True
    assert payload["overridden_plan_arguments"] == ["filename", "target"]

    lookup_response = client.get(f"/api/query/agent/runs/{payload['run_id']}")

    assert lookup_response.status_code == 200
    lookup_payload = lookup_response.json()
    assert lookup_payload["run_id"] == payload["run_id"]
    assert (
        lookup_payload["resumed_from_question"]
        == "Search docs for payment-service outage and summarize top 2 results"
    )
    assert lookup_payload["source_run_id"] is None
    assert lookup_payload["resume_source_type"] == "original_question"
    assert lookup_payload["resume_strategy"] == "search_then_summarize_resume"
    assert lookup_payload["applied_clarification_fields"] == [
        "document_scope",
        "search_query_refinement",
    ]
    assert lookup_payload["question_rewritten"] is True
    assert lookup_payload["overridden_plan_arguments"] == ["filename", "target"]
    assert lookup_payload["question"] == "Search rag_overview.md for RAG and summarize top 2 results"
    assert lookup_payload["started_at"]
    assert lookup_payload["completed_at"]
    assert lookup_payload["last_updated_at"] == lookup_payload["completed_at"]
    persisted_runs = json.loads(workflow_run_store_path.read_text(encoding="utf-8"))
    assert len(persisted_runs) == 1


def test_resume_agent_endpoint_supports_run_id_as_resume_source(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "notes.md").write_text(
        "This file only mentions deployment workflows.",
        encoding="utf-8",
    )
    (raw_dir / "rag_overview.md").write_text(
        "Retrieval-augmented generation, or RAG, is a system pattern that combines document retrieval with language model generation.",
        encoding="utf-8",
    )
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )

    client = TestClient(app)
    initial_response = client.post(
        "/api/query/agent",
        json={
            "question": "Search docs for payment-service outage and summarize top 2 results",
        },
    )

    assert initial_response.status_code == 200
    initial_payload = initial_response.json()
    assert initial_payload["workflow_status"] == "clarification_required"
    assert initial_payload["run_id"]

    resumed_response = client.post(
        "/api/query/agent/resume",
        json={
            "run_id": initial_payload["run_id"],
            "clarification_context": {
                "search_query_refinement": "RAG",
                "document_scope": "rag_overview.md",
            },
        },
    )

    assert resumed_response.status_code == 200
    resumed_payload = resumed_response.json()
    assert resumed_payload["workflow_status"] == "completed"
    assert resumed_payload["resumed_from_question"] == (
        "Search docs for payment-service outage and summarize top 2 results"
    )
    assert resumed_payload["source_run_id"] == initial_payload["run_id"]
    assert resumed_payload["resume_source_type"] == "run_id"
    assert resumed_payload["resume_strategy"] == "search_then_summarize_resume"
    assert resumed_payload["applied_clarification_fields"] == [
        "document_scope",
        "search_query_refinement",
    ]
    assert resumed_payload["question_rewritten"] is True
    assert resumed_payload["overridden_plan_arguments"] == ["filename", "target"]
    assert resumed_payload["question"] == "Search rag_overview.md for RAG and summarize top 2 results"
    assert resumed_payload["tool_plan"]["arguments"]["filename"] == "rag_overview.md"


def test_resume_agent_endpoint_can_resume_failed_search_then_ticket_from_step_two(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text(
        "RAG reduces hallucinations and improves factual grounding.",
        encoding="utf-8",
    )
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"
    ticket_store_path = workspace_tmp_path / "tickets.json"

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    client = TestClient(app)
    initial_response = client.post(
        "/api/query/agent",
        json={
            "question": (
                "Search docs for RAG and create a high severity ticket "
                "for payment-service"
            ),
            "debug_fault_injection": {
                "tool_execution_failures": [
                    {
                        "tool_name": "ticketing",
                        "action": "create",
                        "fail_count": 2,
                        "message": "debug injected persistent failure",
                    }
                ]
            },
        },
    )

    assert initial_response.status_code == 200
    initial_payload = initial_response.json()
    assert initial_payload["workflow_status"] == "failed"
    assert initial_payload["step_count"] == 2
    assert initial_payload["tool_chain"][0]["step_status"] == "completed"
    assert initial_payload["tool_chain"][1]["step_status"] == "failed"

    resumed_response = client.post(
        "/api/query/agent/resume",
        json={
            "run_id": initial_payload["run_id"],
            "clarification_context": {},
        },
    )

    assert resumed_response.status_code == 200
    resumed_payload = resumed_response.json()
    assert resumed_payload["workflow_status"] == "completed"
    assert resumed_payload["source_run_id"] == initial_payload["run_id"]
    assert resumed_payload["resume_source_type"] == "run_id"
    assert resumed_payload["resume_strategy"] == "search_then_ticket_failed_step_resume"
    assert resumed_payload["resumed_from_step_index"] == 2
    assert resumed_payload["reused_step_indices"] == [1]
    assert resumed_payload["question_rewritten"] is False
    assert resumed_payload["applied_clarification_fields"] == []
    assert resumed_payload["tool_chain"][0]["step_index"] == 2
    assert resumed_payload["tool_chain"][0]["tool_plan"]["tool_name"] == "ticketing"
    assert resumed_payload["tool_chain"][0]["tool_execution"]["output"]["supporting_query"] == "RAG"
    assert any(event["stage"] == "resume_reuse" for event in resumed_payload["workflow_trace"])


def test_resume_agent_endpoint_can_resume_failed_status_then_ticket_from_step_two(
    workspace_tmp_path,
    monkeypatch,
):
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"
    ticket_store_path = workspace_tmp_path / "tickets.json"

    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    client = TestClient(app)
    initial_response = client.post(
        "/api/query/agent",
        json={
            "question": (
                "Check system status for payment-service and create a high severity ticket "
                "for payment-service"
            ),
            "debug_fault_injection": {
                "tool_execution_failures": [
                    {
                        "tool_name": "ticketing",
                        "action": "create",
                        "fail_count": 2,
                        "message": "debug injected persistent failure",
                    }
                ]
            },
        },
    )

    assert initial_response.status_code == 200
    initial_payload = initial_response.json()
    assert initial_payload["workflow_status"] == "failed"
    assert initial_payload["tool_chain"][0]["step_status"] == "completed"
    assert initial_payload["tool_chain"][1]["step_status"] == "failed"

    resumed_response = client.post(
        "/api/query/agent/resume",
        json={
            "run_id": initial_payload["run_id"],
            "clarification_context": {
                "environment": "production",
            },
        },
    )

    assert resumed_response.status_code == 200
    resumed_payload = resumed_response.json()
    assert resumed_payload["workflow_status"] == "completed"
    assert resumed_payload["resume_strategy"] == "status_then_ticket_failed_step_resume"
    assert resumed_payload["resumed_from_step_index"] == 2
    assert resumed_payload["reused_step_indices"] == [1]
    assert resumed_payload["applied_clarification_fields"] == ["environment"]
    assert resumed_payload["overridden_plan_arguments"] == ["environment"]
    assert resumed_payload["tool_chain"][0]["step_index"] == 2
    assert resumed_payload["tool_chain"][0]["tool_plan"]["arguments"]["supporting_status"] == "ok"
    assert resumed_payload["tool_chain"][0]["tool_execution"]["output"]["environment"] == "production"
    assert "supporting_summary" in resumed_payload["tool_chain"][0]["tool_execution"]["output"]
    assert any(event["stage"] == "tool_context" for event in resumed_payload["workflow_trace"])


def test_resume_agent_endpoint_can_resume_failed_search_then_summarize_from_step_two(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text(
        "RAG combines document retrieval with language model generation.",
        encoding="utf-8",
    )
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"

    real_build_search_summary = (
        __import__("app.services.agent.orchestrator_service", fromlist=["_build_search_summary"])
        ._build_search_summary
    )

    def fail_search_summary(*args, **kwargs):
        raise RuntimeError("simulated search summary failure")

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service._build_search_summary",
        fail_search_summary,
    )

    client = TestClient(app)
    initial_response = client.post(
        "/api/query/agent",
        json={
            "question": "Search docs for RAG and summarize top 1 results",
        },
    )

    assert initial_response.status_code == 200
    initial_payload = initial_response.json()
    assert initial_payload["workflow_status"] == "failed"
    assert initial_payload["terminal_reason"] == "search_summary_failed"
    assert initial_payload["failure_stage"] == "search_summary"
    assert initial_payload["recommended_recovery_action"] == "resume_from_failed_step"
    assert initial_payload["available_recovery_actions"] == [
        "resume_from_failed_step",
        "manual_retrigger",
    ]
    assert initial_payload["recovery_action_details"] == {
        "resume_from_failed_step": {
            "workflow_kind": "search_then_summarize",
            "target_step_index": 2,
            "reused_step_indices": [1],
        },
        "manual_retrigger": {
            "restarts_workflow": True,
        },
    }
    assert initial_payload["tool_chain"][0]["step_status"] == "completed"

    monkeypatch.setattr(
        "app.services.agent.orchestrator_service._build_search_summary",
        real_build_search_summary,
    )

    resumed_response = client.post(
        "/api/query/agent/resume",
        json={
            "run_id": initial_payload["run_id"],
            "clarification_context": {},
        },
    )

    assert resumed_response.status_code == 200
    resumed_payload = resumed_response.json()
    assert resumed_payload["workflow_status"] == "completed"
    assert resumed_payload["resume_strategy"] == "search_then_summarize_failed_step_resume"
    assert resumed_payload["resumed_from_step_index"] == 2
    assert resumed_payload["reused_step_indices"] == [1]
    assert resumed_payload["answer_source"] == "local_search_summary"
    assert resumed_payload["question_rewritten"] is False
    assert resumed_payload["tool_chain"][0]["step_index"] == 1
    assert any(event["stage"] == "resume_reuse" for event in resumed_payload["workflow_trace"])
    assert any(event["stage"] == "search_summary" for event in resumed_payload["workflow_trace"])


def test_resume_agent_endpoint_can_resume_failed_status_then_summarize_from_step_two(
    workspace_tmp_path,
    monkeypatch,
):
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"

    real_build_status_summary = (
        __import__("app.services.agent.orchestrator_service", fromlist=["_build_status_summary"])
        ._build_status_summary
    )

    def fail_status_summary(*args, **kwargs):
        raise RuntimeError("simulated status summary failure")

    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service._build_status_summary",
        fail_status_summary,
    )

    client = TestClient(app)
    initial_response = client.post(
        "/api/query/agent",
        json={
            "question": "Check system status for payment-service and summarize the result",
        },
    )

    assert initial_response.status_code == 200
    initial_payload = initial_response.json()
    assert initial_payload["workflow_status"] == "failed"
    assert initial_payload["terminal_reason"] == "status_summary_failed"
    assert initial_payload["failure_stage"] == "status_summary"
    assert initial_payload["recommended_recovery_action"] == "resume_from_failed_step"
    assert initial_payload["available_recovery_actions"] == [
        "resume_from_failed_step",
        "manual_retrigger",
    ]
    assert initial_payload["recovery_action_details"] == {
        "resume_from_failed_step": {
            "workflow_kind": "status_then_summarize",
            "target_step_index": 2,
            "reused_step_indices": [1],
        },
        "manual_retrigger": {
            "restarts_workflow": True,
        },
    }
    assert initial_payload["tool_chain"][0]["step_status"] == "completed"

    monkeypatch.setattr(
        "app.services.agent.orchestrator_service._build_status_summary",
        real_build_status_summary,
    )

    resumed_response = client.post(
        "/api/query/agent/resume",
        json={
            "run_id": initial_payload["run_id"],
            "clarification_context": {},
        },
    )

    assert resumed_response.status_code == 200
    resumed_payload = resumed_response.json()
    assert resumed_payload["workflow_status"] == "completed"
    assert resumed_payload["resume_strategy"] == "status_then_summarize_failed_step_resume"
    assert resumed_payload["resumed_from_step_index"] == 2
    assert resumed_payload["reused_step_indices"] == [1]
    assert resumed_payload["answer_source"] == "local_status_summary"
    assert resumed_payload["tool_chain"][0]["step_index"] == 1
    assert any(event["stage"] == "resume_reuse" for event in resumed_payload["workflow_trace"])
    assert any(event["stage"] == "status_summary" for event in resumed_payload["workflow_trace"])


def test_resume_agent_endpoint_returns_clear_error_for_completed_run_without_clarification(
    workspace_tmp_path,
    monkeypatch,
):
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"

    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )

    client = TestClient(app)
    initial_response = client.post(
        "/api/query/agent",
        json={
            "question": "Create a ticket for the payment service outage",
        },
    )

    assert initial_response.status_code == 200
    initial_payload = initial_response.json()
    assert initial_payload["workflow_status"] == "completed"

    resumed_response = client.post(
        "/api/query/agent/resume",
        json={
            "run_id": initial_payload["run_id"],
            "clarification_context": {},
        },
    )

    assert resumed_response.status_code == 400
    assert resumed_response.json()["detail"] == "source_run_not_failed_step_resumable"


def test_resume_agent_endpoint_returns_clear_error_for_non_eligible_failed_run_without_clarification(
    workspace_tmp_path,
    monkeypatch,
):
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"

    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )

    client = TestClient(app)
    initial_response = client.post(
        "/api/query/agent",
        json={
            "question": "Create a ticket for the payment service outage",
            "debug_fault_injection": {
                "tool_execution_failures": [
                    {
                        "tool_name": "ticketing",
                        "action": "create",
                        "fail_count": 2,
                        "message": "debug injected persistent failure",
                    }
                ]
            },
        },
    )

    assert initial_response.status_code == 200
    initial_payload = initial_response.json()
    assert initial_payload["workflow_status"] == "failed"
    assert initial_payload["step_count"] == 1

    resumed_response = client.post(
        "/api/query/agent/resume",
        json={
            "run_id": initial_payload["run_id"],
            "clarification_context": {},
        },
    )

    assert resumed_response.status_code == 400
    assert resumed_response.json()["detail"] == "source_run_not_eligible_for_failed_step_resume"


def test_recover_agent_endpoint_uses_recommended_failed_step_resume(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text(
        "RAG reduces hallucinations and improves factual grounding.",
        encoding="utf-8",
    )
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"
    ticket_store_path = workspace_tmp_path / "tickets.json"

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    client = TestClient(app)
    initial_response = client.post(
        "/api/query/agent",
        json={
            "question": (
                "Search docs for RAG and create a high severity ticket "
                "for payment-service"
            ),
            "debug_fault_injection": {
                "tool_execution_failures": [
                    {
                        "tool_name": "ticketing",
                        "action": "create",
                        "fail_count": 2,
                        "message": "debug injected persistent failure",
                    }
                ]
            },
        },
    )

    assert initial_response.status_code == 200
    initial_payload = initial_response.json()
    assert initial_payload["root_run_id"] == initial_payload["run_id"]
    assert initial_payload["recovery_depth"] == 0
    assert initial_payload["recommended_recovery_action"] == "resume_from_failed_step"

    recovered_response = client.post(
        "/api/query/agent/recover",
        json={
            "run_id": initial_payload["run_id"],
        },
    )

    assert recovered_response.status_code == 200
    recovered_payload = recovered_response.json()
    assert recovered_payload["workflow_status"] == "completed"
    assert recovered_payload["recovered_via_action"] == "resume_from_failed_step"
    assert recovered_payload["resume_strategy"] == "search_then_ticket_failed_step_resume"
    assert recovered_payload["source_run_id"] == initial_payload["run_id"]
    assert recovered_payload["root_run_id"] == initial_payload["run_id"]
    assert recovered_payload["recovery_depth"] == 1
    assert recovered_payload["resume_source_type"] == "run_id"


def test_recover_agent_endpoint_manual_retriggers_single_step_failures(
    workspace_tmp_path,
    monkeypatch,
):
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"
    ticket_store_path = workspace_tmp_path / "tickets.json"

    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    client = TestClient(app)
    initial_response = client.post(
        "/api/query/agent",
        json={
            "question": "Create a ticket for the payment service outage",
            "debug_fault_injection": {
                "tool_execution_failures": [
                    {
                        "tool_name": "ticketing",
                        "action": "create",
                        "fail_count": 2,
                        "message": "debug injected persistent failure",
                    }
                ]
            },
        },
    )

    assert initial_response.status_code == 200
    initial_payload = initial_response.json()
    assert initial_payload["root_run_id"] == initial_payload["run_id"]
    assert initial_payload["recovery_depth"] == 0
    assert initial_payload["recommended_recovery_action"] == "manual_retrigger"

    recovered_response = client.post(
        "/api/query/agent/recover",
        json={
            "run_id": initial_payload["run_id"],
        },
    )

    assert recovered_response.status_code == 200
    recovered_payload = recovered_response.json()
    assert recovered_payload["workflow_status"] == "completed"
    assert recovered_payload["recovered_via_action"] == "manual_retrigger"
    assert recovered_payload["resume_strategy"] == "manual_retrigger_recovery"
    assert recovered_payload["source_run_id"] == initial_payload["run_id"]
    assert recovered_payload["root_run_id"] == initial_payload["run_id"]
    assert recovered_payload["recovery_depth"] == 1
    assert recovered_payload["resume_source_type"] == "run_id"
    assert any(event["stage"] == "workflow_recovery" for event in recovered_payload["workflow_trace"])


def test_recover_agent_endpoint_rejects_unavailable_recovery_action(
    workspace_tmp_path,
    monkeypatch,
):
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"
    ticket_store_path = workspace_tmp_path / "tickets.json"

    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    client = TestClient(app)
    initial_response = client.post(
        "/api/query/agent",
        json={
            "question": "Create a ticket for the payment service outage",
            "debug_fault_injection": {
                "tool_execution_failures": [
                    {
                        "tool_name": "ticketing",
                        "action": "create",
                        "fail_count": 2,
                        "message": "debug injected persistent failure",
                    }
                ]
            },
        },
    )

    assert initial_response.status_code == 200
    initial_payload = initial_response.json()

    recovered_response = client.post(
        "/api/query/agent/recover",
        json={
            "run_id": initial_payload["run_id"],
            "recovery_action": "resume_from_failed_step",
        },
    )

    assert recovered_response.status_code == 400
    assert recovered_response.json()["detail"] == "recovery_action_not_available"


def test_resume_agent_endpoint_requires_original_question_or_run_id():
    client = TestClient(app)
    response = client.post(
        "/api/query/agent/resume",
        json={
            "clarification_context": {
                "search_query_refinement": "RAG",
            },
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "original_question_or_run_id_required"


def test_list_agent_workflow_runs_endpoint_returns_latest_runs_with_limit(
    workspace_tmp_path,
    monkeypatch,
):
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"
    ticket_store_path = workspace_tmp_path / "tickets.json"

    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    client = TestClient(app)
    first_response = client.post(
        "/api/query/agent",
        json={"question": "Check system status"},
    )
    second_response = client.post(
        "/api/query/agent",
        json={"question": "Create a ticket for the payment service outage"},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_run_id = first_response.json()["run_id"]
    second_run_id = second_response.json()["run_id"]

    list_response = client.get("/api/query/agent/runs?limit=1")

    assert list_response.status_code == 200
    payload = list_response.json()
    assert len(payload["runs"]) == 1
    assert payload["runs"][0]["run_id"] == second_run_id
    assert payload["runs"][0]["question"] == "Create a ticket for the payment service outage"
    assert payload["runs"][0]["route_type"] == "tool_execution"
    assert payload["runs"][0]["terminal_reason"] == "tool_execution_completed"
    assert payload["runs"][0]["outcome_category"] == "completed"
    assert payload["runs"][0]["is_recoverable"] is False
    assert payload["runs"][0]["retry_state"] == "not_applicable"
    assert payload["runs"][0]["recommended_recovery_action"] == "none"
    assert payload["runs"][0]["available_recovery_actions"] == []
    assert payload["runs"][0]["root_run_id"] == second_run_id
    assert payload["runs"][0]["recovery_depth"] == 0
    assert payload["runs"][0]["resumed_from_question"] is None
    assert payload["runs"][0]["source_run_id"] is None
    assert payload["runs"][0]["resume_source_type"] is None
    assert payload["runs"][0]["resume_strategy"] is None
    assert payload["runs"][0]["resumed_from_step_index"] is None
    assert payload["runs"][0]["reused_step_indices"] == []
    assert payload["runs"][0]["applied_clarification_fields"] == []
    assert payload["runs"][0]["question_rewritten"] is False
    assert payload["runs"][0]["overridden_plan_arguments"] == []
    assert payload["runs"][0]["step_count"] == 1
    assert payload["runs"][0]["started_at"]
    assert payload["runs"][0]["completed_at"]
    assert payload["runs"][0]["last_updated_at"] == payload["runs"][0]["completed_at"]
    assert payload["runs"][0]["answer_source"] is None
    assert payload["runs"][0]["workflow_planning_mode"] is None
    assert payload["runs"][0]["tool_planning_mode"] == "heuristic_stub"
    assert payload["runs"][0]["tool_planning_modes"] == ["heuristic_stub"]
    assert payload["runs"][0]["clarification_planning_mode"] is None
    assert payload["runs"][0]["planner_call_count"] == 1
    assert payload["runs"][0]["tool_planner_call_count"] == 1
    assert payload["runs"][0]["workflow_planning_latency_ms"] == 0
    assert payload["runs"][0]["tool_planning_latency_ms"] == 0
    assert payload["runs"][0]["clarification_planning_latency_ms"] == 0
    assert payload["runs"][0]["planner_latency_ms_total"] == 0
    assert payload["runs"][0]["llm_planner_layers"] == []
    assert payload["runs"][0]["fallback_planner_layers"] == ["tool"]
    assert payload["runs"][0]["llm_tool_planner_steps"] == []
    assert payload["runs"][0]["fallback_tool_planner_steps"] == [1]
    assert payload["runs"][0]["final_tool_name"] == "ticketing"
    assert payload["runs"][0]["final_tool_action"] == "create"
    assert payload["runs"][0]["run_id"] != first_run_id


def test_list_agent_workflow_runs_endpoint_marks_failed_step_resume_eligible_runs(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text(
        "RAG combines document retrieval with language model generation.",
        encoding="utf-8",
    )
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"
    ticket_store_path = workspace_tmp_path / "tickets.json"

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )
    monkeypatch.setattr("app.services.agent.tool_service.TICKET_STORE_PATH", ticket_store_path)

    client = TestClient(app)
    response = client.post(
        "/api/query/agent",
        json={
            "question": "Search docs for RAG and create a high severity ticket for payment-service",
            "debug_fault_injection": {
                "tool_execution_failures": [
                    {
                        "tool_name": "ticketing",
                        "action": "create",
                        "fail_count": 2,
                        "message": "debug injected persistent failure",
                    }
                ]
            },
        },
    )

    assert response.status_code == 200
    list_response = client.get("/api/query/agent/runs?limit=1")

    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["runs"][0]["workflow_status"] == "failed"
    assert payload["runs"][0]["root_run_id"] == payload["runs"][0]["run_id"]
    assert payload["runs"][0]["recovery_depth"] == 0
    assert payload["runs"][0]["resumed_from_step_index"] is None
    assert payload["runs"][0]["reused_step_indices"] == []
    assert payload["runs"][0]["retry_state"] == "retry_exhausted"
    assert payload["runs"][0]["recommended_recovery_action"] == "resume_from_failed_step"
    assert payload["runs"][0]["available_recovery_actions"] == [
        "resume_from_failed_step",
        "manual_retrigger",
    ]
    assert payload["runs"][0]["recovery_action_details"] == {
        "resume_from_failed_step": {
            "workflow_kind": "search_then_ticket",
            "target_step_index": 2,
            "reused_step_indices": [1],
        },
        "manual_retrigger": {
            "restarts_workflow": True,
        },
    }


def test_list_agent_workflow_runs_endpoint_recovers_from_invalid_store(
    workspace_tmp_path,
    monkeypatch,
):
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"
    workflow_run_store_path.write_text("{invalid json", encoding="utf-8")

    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )

    client = TestClient(app)
    list_response = client.get("/api/query/agent/runs?limit=5")

    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["runs"] == []

    create_response = client.post(
        "/api/query/agent",
        json={"question": "Check system status"},
    )

    assert create_response.status_code == 200
    persisted_runs = json.loads(workflow_run_store_path.read_text(encoding="utf-8"))
    assert len(persisted_runs) == 1
    assert persisted_runs[0]["question"] == "Check system status"


def test_list_agent_workflow_runs_endpoint_normalizes_legacy_tool_chain(
    workspace_tmp_path,
    monkeypatch,
):
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"
    workflow_run_store_path.write_text(
        json.dumps(
            [
                {
                    "run_id": "legacy-run-1",
                    "question": "Search docs for reranking and create a ticket",
                    "workflow_status": "completed",
                    "route": {
                        "route_type": "tool_execution",
                        "route_reason": "legacy route",
                        "filename": None,
                    },
                    "workflow_trace": [
                        {
                            "stage": "routing",
                            "status": "completed",
                            "timestamp": "2026-03-15T16:12:37.485983+00:00",
                            "detail": "Request routed to tool_execution.",
                        },
                        {
                            "stage": "tool_execution",
                            "status": "completed",
                            "timestamp": "2026-03-15T16:12:37.487903+00:00",
                            "detail": "Executed local_adapter tool document_search:query with status completed.",
                        },
                    ],
                    "tool_chain": [
                        {
                            "question": "Search docs for reranking",
                            "tool_plan": {"tool_name": "document_search"},
                            "tool_execution": {
                                "execution_status": "completed",
                                "executed_at": "2026-03-15T16:12:37.487871+00:00",
                            },
                        },
                        {
                            "question": "create a ticket",
                            "tool_plan": {"tool_name": "ticketing"},
                            "tool_execution": {
                                "execution_status": "completed",
                                "executed_at": "2026-03-15T16:12:38.000000+00:00",
                            },
                        },
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )

    client = TestClient(app)
    response = client.get("/api/query/agent/runs?limit=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runs"][0]["run_id"] == "legacy-run-1"


def test_get_agent_workflow_run_endpoint_normalizes_legacy_tool_chain(
    workspace_tmp_path,
    monkeypatch,
):
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"
    workflow_run_store_path.write_text(
        json.dumps(
            [
                {
                    "run_id": "legacy-run-2",
                    "question": "Search docs for reranking and create a ticket",
                    "workflow_status": "completed",
                    "route": {
                        "route_type": "tool_execution",
                        "route_reason": "legacy route",
                        "filename": None,
                    },
                    "workflow_trace": [
                        {
                            "stage": "routing",
                            "status": "completed",
                            "timestamp": "2026-03-15T16:12:37.485983+00:00",
                            "detail": "Request routed to tool_execution.",
                        },
                        {
                            "stage": "tool_execution",
                            "status": "completed",
                            "timestamp": "2026-03-15T16:12:37.487903+00:00",
                            "detail": "Executed local_adapter tool document_search:query with status completed.",
                        },
                    ],
                    "tool_chain": [
                        {
                            "question": "Search docs for reranking",
                            "tool_plan": {"tool_name": "document_search"},
                            "tool_execution": {
                                "execution_status": "completed",
                                "executed_at": "2026-03-15T16:12:37.487871+00:00",
                            },
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )

    client = TestClient(app)
    response = client.get("/api/query/agent/runs/legacy-run-2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "legacy-run-2"
    assert payload["tool_chain"][0]["step_id"] == "step_1"
    assert payload["tool_chain"][0]["step_index"] == 1
    assert payload["tool_chain"][0]["step_status"] == "completed"
    assert payload["tool_chain"][0]["started_at"] == "2026-03-15T16:12:37.487871+00:00"
    assert payload["step_count"] == 1
    assert payload["started_at"] == "2026-03-15T16:12:37.485983+00:00"
    assert payload["completed_at"] == "2026-03-15T16:12:37.487903+00:00"
    assert payload["last_updated_at"] == "2026-03-15T16:12:37.487903+00:00"
    assert payload["terminal_reason"] == "tool_execution_completed"


def test_migrate_agent_workflow_runs_endpoint_upgrades_legacy_tool_chain(
    workspace_tmp_path,
    monkeypatch,
):
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"
    workflow_run_store_path.write_text(
        json.dumps(
            [
                {
                    "run_id": "legacy-run-migrate",
                    "question": "Search docs for reranking and create a ticket",
                    "workflow_status": "completed",
                    "route": {
                        "route_type": "tool_execution",
                        "route_reason": "legacy route",
                        "filename": None,
                    },
                    "workflow_trace": [
                        {
                            "stage": "routing",
                            "status": "completed",
                            "timestamp": "2026-03-15T16:12:37.485983+00:00",
                            "detail": "Request routed to tool_execution.",
                        },
                        {
                            "stage": "tool_execution",
                            "status": "completed",
                            "timestamp": "2026-03-15T16:12:37.487903+00:00",
                            "detail": "Executed local_adapter tool document_search:query with status completed.",
                        },
                    ],
                    "tool_chain": [
                        {
                            "question": "Search docs for reranking",
                            "tool_plan": {"tool_name": "document_search"},
                            "tool_execution": {
                                "execution_status": "completed",
                                "executed_at": "2026-03-15T16:12:37.487871+00:00",
                            },
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )

    client = TestClient(app)
    response = client.post("/api/query/agent/runs/migrate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["migrated_run_count"] == 1
    assert payload["migrated_step_count"] == 1
    assert payload["total_run_count"] == 1

    persisted_runs = json.loads(workflow_run_store_path.read_text(encoding="utf-8"))
    assert persisted_runs[0]["tool_chain"][0]["step_id"] == "step_1"
    assert persisted_runs[0]["tool_chain"][0]["step_index"] == 1
    assert persisted_runs[0]["step_count"] == 1
    assert persisted_runs[0]["started_at"] == "2026-03-15T16:12:37.485983+00:00"
    assert persisted_runs[0]["completed_at"] == "2026-03-15T16:12:37.487903+00:00"
    assert persisted_runs[0]["last_updated_at"] == "2026-03-15T16:12:37.487903+00:00"
    assert persisted_runs[0]["terminal_reason"] == "tool_execution_completed"


def test_migrate_agent_workflow_runs_endpoint_is_noop_for_current_schema(
    workspace_tmp_path,
    monkeypatch,
):
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"
    workflow_run_store_path.write_text(
        json.dumps(
            [
                    {
                        "run_id": "current-run",
                        "root_run_id": "current-run",
                        "recovery_depth": 0,
                        "question": "Check system status",
                        "workflow_status": "completed",
                        "terminal_reason": "tool_execution_completed",
                        "outcome_category": "completed",
                        "is_recoverable": False,
                        "retry_state": "not_applicable",
                        "recommended_recovery_action": "none",
                        "available_recovery_actions": [],
                        "recovery_action_details": {},
                        "resumed_from_step_index": None,
                        "reused_step_indices": [],
                    "started_at": "2026-03-15T16:12:37.485983+00:00",
                        "completed_at": "2026-03-15T16:12:37.487903+00:00",
                        "last_updated_at": "2026-03-15T16:12:37.487903+00:00",
                        "workflow_planning_mode": None,
                        "tool_planning_mode": None,
                        "tool_planning_modes": [],
                        "clarification_planning_mode": None,
                        "planner_call_count": 0,
                        "tool_planner_call_count": 0,
                        "workflow_planning_latency_ms": 0,
                        "tool_planning_latency_ms": 0,
                        "clarification_planning_latency_ms": 0,
                        "planner_latency_ms_total": 0,
                        "llm_planner_layers": [],
                        "fallback_planner_layers": [],
                        "llm_tool_planner_steps": [],
                        "fallback_tool_planner_steps": [],
                        "retry_count": 0,
                        "retried_step_indices": [],
                        "step_count": 1,
                    "route": {
                        "route_type": "tool_execution",
                        "route_reason": "current route",
                        "filename": None,
                    },
                    "workflow_trace": [],
                    "tool_chain": [
                        {
                                "step_id": "step_1",
                                "step_index": 1,
                                "step_status": "completed",
                                "attempt_count": 1,
                                "retried": False,
                                "started_at": "2026-03-15T16:12:37.487871+00:00",
                                "completed_at": "2026-03-15T16:12:37.487871+00:00",
                                "question": "Check system status",
                            "tool_plan": {"tool_name": "system_status"},
                            "tool_execution": {
                                "execution_status": "completed",
                                "executed_at": "2026-03-15T16:12:37.487871+00:00",
                            },
                            "failure_message": None,
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )

    client = TestClient(app)
    response = client.post("/api/query/agent/runs/migrate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["migrated_run_count"] == 0
    assert payload["migrated_step_count"] == 0
    assert payload["total_run_count"] == 1


def test_list_agent_workflow_runs_endpoint_includes_resume_metadata(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rag_overview.md").write_text(
        "Retrieval-augmented generation, or RAG, combines retrieval and generation.",
        encoding="utf-8",
    )
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )

    client = TestClient(app)
    resumed_response = client.post(
        "/api/query/agent/resume",
        json={
            "original_question": "Search docs for payment-service outage and summarize top 2 results",
            "clarification_context": {
                "search_query_refinement": "RAG",
                "document_scope": "rag_overview.md",
            },
        },
    )

    assert resumed_response.status_code == 200

    list_response = client.get("/api/query/agent/runs?limit=1")

    assert list_response.status_code == 200
    payload = list_response.json()
    assert len(payload["runs"]) == 1
    assert payload["runs"][0]["resume_source_type"] == "original_question"
    assert payload["runs"][0]["resume_strategy"] == "search_then_summarize_resume"
    assert payload["runs"][0]["applied_clarification_fields"] == [
        "document_scope",
        "search_query_refinement",
    ]
    assert payload["runs"][0]["question_rewritten"] is True
    assert payload["runs"][0]["overridden_plan_arguments"] == ["filename", "target"]
    assert payload["runs"][0]["step_count"] == 1
    assert payload["runs"][0]["answer_source"] == "local_search_summary"
    assert payload["runs"][0]["final_tool_name"] == "document_search"
    assert payload["runs"][0]["final_tool_action"] == "query"


def test_list_agent_workflow_runs_endpoint_rejects_non_positive_limit():
    client = TestClient(app)
    response = client.get("/api/query/agent/runs?limit=0")

    assert response.status_code == 400
    assert response.json()["detail"] == "limit_must_be_positive"


def test_get_agent_workflow_run_stats_endpoint_returns_summary_counts(
    workspace_tmp_path,
    monkeypatch,
):
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"
    workflow_run_store_path.write_text(
        json.dumps(
            [
                {
                    "run_id": "run-1",
                    "question": "Check system status",
                    "workflow_status": "completed",
                    "terminal_reason": "tool_execution_completed",
                    "started_at": "2026-03-15T10:00:00+00:00",
                    "completed_at": "2026-03-15T10:00:01+00:00",
                    "last_updated_at": "2026-03-15T10:00:01+00:00",
                    "step_count": 1,
                    "route": {
                        "route_type": "tool_execution",
                        "route_reason": "route 1",
                        "filename": None,
                    },
                    "workflow_trace": [],
                    "tool_chain": [],
                },
                {
                    "run_id": "run-2",
                    "question": "Please do that for production",
                    "workflow_status": "clarification_required",
                    "terminal_reason": "clarification_requested",
                    "started_at": "2026-03-15T10:01:00+00:00",
                    "completed_at": None,
                    "last_updated_at": "2026-03-15T10:01:01+00:00",
                    "step_count": 0,
                    "route": {
                        "route_type": "clarification_needed",
                        "route_reason": "route 2",
                        "filename": None,
                    },
                    "workflow_trace": [],
                    "tool_chain": [],
                },
                {
                    "run_id": "run-3",
                    "question": "Broken run",
                    "workflow_status": "failed",
                    "terminal_reason": "tool_execution_failed",
                    "started_at": "2026-03-15T10:02:00+00:00",
                    "completed_at": "2026-03-15T10:02:03+00:00",
                    "last_updated_at": "2026-03-15T10:02:03+00:00",
                    "step_count": 1,
                    "route": {
                        "route_type": "tool_execution",
                        "route_reason": "route 3",
                        "filename": None,
                    },
                    "workflow_trace": [],
                    "tool_chain": [],
                },
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )

    client = TestClient(app)
    response = client.get("/api/query/agent/runs/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "total_run_count": 3,
        "completed_run_count": 1,
        "clarification_required_run_count": 1,
        "failed_run_count": 1,
        "latest_run_id": "run-3",
        "latest_updated_at": "2026-03-15T10:02:03+00:00",
    }


def test_get_agent_workflow_run_endpoint_backfills_recovery_semantics_for_unknown_failed_reason(
    workspace_tmp_path,
    monkeypatch,
):
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"
    workflow_run_store_path.write_text(
        json.dumps(
            [
                {
                    "run_id": "run-unknown-failure",
                    "question": "Broken run",
                    "workflow_status": "failed",
                    "terminal_reason": "unexpected_runtime_state",
                    "failure_stage": "runtime",
                    "failure_message": "unexpected state encountered",
                    "started_at": "2026-03-15T10:02:00+00:00",
                    "completed_at": "2026-03-15T10:02:03+00:00",
                    "last_updated_at": "2026-03-15T10:02:03+00:00",
                    "step_count": 1,
                    "route": {
                        "route_type": "tool_execution",
                        "route_reason": "route 3",
                        "filename": None,
                    },
                    "workflow_trace": [],
                    "tool_chain": [],
                },
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )

    client = TestClient(app)
    response = client.get("/api/query/agent/runs/run-unknown-failure")

    assert response.status_code == 200
    payload = response.json()
    assert payload["terminal_reason"] == "unexpected_runtime_state"
    assert payload["outcome_category"] == "non_recoverable_failure"
    assert payload["is_recoverable"] is False
    assert payload["retry_state"] == "not_applicable"
    assert payload["recommended_recovery_action"] == "manual_investigation"


def test_prune_agent_workflow_runs_endpoint_keeps_latest_runs(
    workspace_tmp_path,
    monkeypatch,
):
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"
    workflow_run_store_path.write_text(
        json.dumps(
            [
                {
                    "run_id": "run-1",
                    "question": "Question 1",
                    "workflow_status": "completed",
                    "route": {
                        "route_type": "tool_execution",
                        "route_reason": "route",
                        "filename": None,
                    },
                    "workflow_trace": [],
                    "tool_chain": [],
                },
                {
                    "run_id": "run-2",
                    "question": "Question 2",
                    "workflow_status": "completed",
                    "route": {
                        "route_type": "tool_execution",
                        "route_reason": "route",
                        "filename": None,
                    },
                    "workflow_trace": [],
                    "tool_chain": [],
                },
                {
                    "run_id": "run-3",
                    "question": "Question 3",
                    "workflow_status": "completed",
                    "route": {
                        "route_type": "tool_execution",
                        "route_reason": "route",
                        "filename": None,
                    },
                    "workflow_trace": [],
                    "tool_chain": [],
                },
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )

    client = TestClient(app)
    response = client.post("/api/query/agent/runs/prune", json={"retain": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "total_run_count_before": 3,
        "retained_run_count": 2,
        "removed_run_count": 1,
    }

    persisted_runs = json.loads(workflow_run_store_path.read_text(encoding="utf-8"))
    assert [run["run_id"] for run in persisted_runs] == ["run-2", "run-3"]


def test_reset_agent_workflow_runs_endpoint_requires_confirmation(
    workspace_tmp_path,
    monkeypatch,
):
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"
    workflow_run_store_path.write_text(
        json.dumps(
            [
                {
                    "run_id": "run-1",
                    "question": "Question 1",
                    "workflow_status": "completed",
                    "route": {
                        "route_type": "tool_execution",
                        "route_reason": "route",
                        "filename": None,
                    },
                    "workflow_trace": [],
                    "tool_chain": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )

    client = TestClient(app)
    response = client.post("/api/query/agent/runs/reset", json={"confirm": False})

    assert response.status_code == 400
    assert response.json()["detail"] == "reset_confirmation_required"
    persisted_runs = json.loads(workflow_run_store_path.read_text(encoding="utf-8"))
    assert len(persisted_runs) == 1


def test_reset_agent_workflow_runs_endpoint_clears_runs_with_confirmation(
    workspace_tmp_path,
    monkeypatch,
):
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"
    workflow_run_store_path.write_text(
        json.dumps(
            [
                {
                    "run_id": "run-1",
                    "question": "Question 1",
                    "workflow_status": "completed",
                    "route": {
                        "route_type": "tool_execution",
                        "route_reason": "route",
                        "filename": None,
                    },
                    "workflow_trace": [],
                    "tool_chain": [],
                },
                {
                    "run_id": "run-2",
                    "question": "Question 2",
                    "workflow_status": "completed",
                    "route": {
                        "route_type": "tool_execution",
                        "route_reason": "route",
                        "filename": None,
                    },
                    "workflow_trace": [],
                    "tool_chain": [],
                },
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )

    client = TestClient(app)
    response = client.post("/api/query/agent/runs/reset", json={"confirm": True})

    assert response.status_code == 200
    assert response.json() == {"removed_run_count": 2}
    persisted_runs = json.loads(workflow_run_store_path.read_text(encoding="utf-8"))
    assert persisted_runs == []


def test_tool_planner_uses_dedicated_gemini_model_when_configured(monkeypatch):
    import httpx

    captured: dict[str, object] = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": __import__("json").dumps(
                                            {
                                                "tool_name": "document_search",
                                                "action": "query",
                                                "target": "RAG",
                                                "arguments": {},
                                            }
                                        )
                                    }
                                ]
                            }
                        }
                    ]
                }

        return FakeResponse()

    monkeypatch.setattr(settings, "tool_planner_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", "configured")
    monkeypatch.setattr(settings, "gemini_chat_model", "gemini-chat-default")
    monkeypatch.setattr(settings, "gemini_tool_planner_model", "gemini-tool-planner")
    monkeypatch.setattr(httpx, "post", fake_post)

    response = plan_tool_request("Search docs for RAG")

    assert response.planning_mode == "llm_gemini"
    assert "gemini-tool-planner:generateContent" in captured["url"]


def test_clarification_planner_uses_dedicated_openai_model_when_configured(monkeypatch):
    import httpx

    captured: dict[str, object] = {}

    def fake_post(url, headers, json, timeout):
        captured["payload"] = json

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "choices": [
                        {
                            "message": {
                                "content": __import__("json").dumps(
                                    {
                                        "missing_fields": ["target", "priority"],
                                        "follow_up_questions": [
                                            "Which service should the agent act on?",
                                            "What severity should the ticket use?",
                                        ],
                                        "clarification_summary": "The request needs more detail before execution.",
                                    }
                                )
                            }
                        }
                    ]
                }

        return FakeResponse()

    monkeypatch.setattr(settings, "clarification_planner_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "configured")
    monkeypatch.setattr(settings, "openai_chat_model", "gpt-chat-default")
    monkeypatch.setattr(settings, "openai_clarification_planner_model", "gpt-clarification-planner")
    monkeypatch.setattr(httpx, "post", fake_post)

    response = plan_clarification("Please do that for production")

    assert response.planning_mode == "llm_openai"
    assert captured["payload"]["model"] == "gpt-clarification-planner"

