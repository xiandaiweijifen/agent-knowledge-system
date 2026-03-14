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

    assert created.execution_status == "completed"
    assert created.output["status"] == "open"
    assert updated.output["severity"] == "medium"
    assert closed.output["status"] == "closed"


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
    assert queried.output["ticket_id"] == created.output["ticket_id"]
    assert queried.output["status"] == "open"


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
    assert listed.output["ticket_count"] == "2"
    assert listed.output["status_filter"] == "open"
    assert "TICKET-0001" in listed.output["tickets"]


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
    assert response.output["embedding_provider"] == "gemini"
    assert response.output["chat_provider"] == "fallback"
    assert response.output["gemini_configured"] == "true"


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
    assert response.target == "reranking"


def test_plan_tool_request_maps_status_queries_to_system_status():
    response = plan_tool_request("Check system status")

    assert response.tool_name == "system_status"
    assert response.action == "query"
    assert response.target == "system status"


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
    assert payload["route"]["route_type"] == "tool_execution"
    assert len(payload["workflow_trace"]) >= 3
    assert payload["tool_plan"]["tool_name"] == "ticketing"
    assert payload["tool_execution"]["execution_status"] == "completed"
    assert any(
        event["stage"] == "tool_execution"
        and "local_adapter tool ticketing:create" in event["detail"]
        for event in payload["workflow_trace"]
    )


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
    assert payload["route"]["route_type"] == "clarification_needed"
    assert len(payload["workflow_trace"]) >= 2
    assert payload["clarification_message"]
    assert "missing_fields" in payload["clarification_plan"]
    assert payload["clarification_plan"]["follow_up_questions"]
