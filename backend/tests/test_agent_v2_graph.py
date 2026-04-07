"""
Tests for the LangGraph agent graph skeleton.
Verifies graph compilation and Package 8 router behavior.
"""

import pytest
from app.services.agent_v2.graph import build_graph
from app.services.agent_v2.state import AgentState


BASE_INPUT: AgentState = {
    "question": "What is LangGraph?",
    "filename": "doc.txt",
    "top_k": 3,
    "route": "",
    "route_reason": None,
    "route_planning_mode": None,
    "retrieval_result": None,
    "tool_chain": [],
    "clarification_question": None,
    "answer": None,
    "answer_source": None,
    "model": None,
    "answered_at": None,
    "answer_latency_ms": None,
    "chat_provider": None,
    "chat_model": None,
    "workflow_status": "in_progress",
    "error": None,
    "messages": [],
}


@pytest.fixture
def graph():
    return build_graph()


def test_graph_compiles(graph):
    assert graph is not None
    assert "router" in graph.nodes
    assert "retrieval" in graph.nodes
    assert "tool_exec" in graph.nodes
    assert "clarify" in graph.nodes
    assert "answer" in graph.nodes


def test_retrieval_path(graph, monkeypatch):
    """Default route → retrieval → answer → END."""
    monkeypatch.setattr(
        "app.services.agent_v2.nodes.retrieval.run_query",
        lambda filename, question, top_k: type(
            "QueryResponse",
            (),
            {
                "answer": "retrieved answer",
                "answer_source": "fallback",
                "model": "gemini-2.5-flash",
                "answered_at": "2026-04-07T00:00:00+00:00",
                "answer_latency_ms": 123.0,
                "chat_provider": "gemini",
                "chat_model": "gemini-2.5-flash",
                "retrieval": type(
                    "RetrievalResult",
                    (),
                    {
                        "model_dump": lambda self: {
                            "filename": filename,
                            "embedding_provider": "gemini",
                            "embedding_model": "gemini-embedding-001",
                            "vector_dim": 3072,
                            "question": question,
                            "top_k": top_k,
                            "retrieved_at": "2026-04-07T00:00:00+00:00",
                            "retrieval_latency_ms": 50.0,
                            "query_embedding_provider": "gemini",
                            "query_embedding_model": "gemini-embedding-001",
                            "matches": [],
                        }
                    },
                )(),
            },
        )(),
    )
    result = graph.invoke(BASE_INPUT)
    assert result["workflow_status"] == "completed"
    assert result["answer"] == "retrieved answer"
    assert result["route"] == "knowledge_retrieval"


def test_tool_exec_path(graph):
    """Pre-set route=tool_execution → tool_exec → answer → END."""
    result = graph.invoke({**BASE_INPUT, "route": "tool_execution"})
    assert result["workflow_status"] == "completed"


def test_clarification_path(graph):
    """Pre-set route=clarification_needed → clarify → END."""
    result = graph.invoke({**BASE_INPUT, "route": "clarification_needed"})
    assert result["workflow_status"] == "clarification_required"
    assert result["clarification_question"] is not None


def test_state_fields_present(graph):
    """All expected fields survive graph execution."""
    result = graph.invoke({**BASE_INPUT, "route": "clarification_needed"})
    for field in ("question", "filename", "top_k", "route", "workflow_status"):
        assert field in result
