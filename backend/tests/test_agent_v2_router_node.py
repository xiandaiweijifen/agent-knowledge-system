from app.services.agent_v2.nodes.router import router_node


BASE_STATE = {
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
    "workflow_status": "in_progress",
    "error": None,
    "messages": [],
}


def test_router_node_uses_llm_route_when_available(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_v2.nodes.router.generate_llm_route_decision",
        lambda question, filename=None: (
            "llm_openai",
            {
                "route": "knowledge_retrieval",
                "route_reason": "This is a document-backed knowledge question.",
            },
        ),
    )
    result = router_node(BASE_STATE)
    assert result == {
        "route": "knowledge_retrieval",
        "route_reason": "This is a document-backed knowledge question.",
        "route_planning_mode": "llm_openai",
        "workflow_status": "in_progress",
    }


def test_router_node_falls_back_to_legacy_router(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_v2.nodes.router.generate_llm_route_decision",
        lambda question, filename=None: ("heuristic_fallback_missing_openai_key", None),
    )
    monkeypatch.setattr(
        "app.services.agent_v2.nodes.router.route_request",
        lambda question, filename=None: type(
            "FallbackDecision",
            (),
            {
                "route_type": "tool_execution",
                "route_reason": "Legacy router matched an execution-style request.",
            },
        )(),
    )
    result = router_node(BASE_STATE)
    assert result == {
        "route": "tool_execution",
        "route_reason": "Legacy router matched an execution-style request.",
        "route_planning_mode": "heuristic_fallback_missing_openai_key",
        "workflow_status": "in_progress",
    }


def test_router_node_preserves_precomputed_route(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_v2.nodes.router.generate_llm_route_decision",
        lambda question, filename=None: ("llm_openai", None),
    )
    result = router_node(
        {
            **BASE_STATE,
            "route": "clarification_needed",
            "route_reason": "Caller already determined this request is ambiguous.",
        }
    )
    assert result == {
        "route": "clarification_needed",
        "route_reason": "Caller already determined this request is ambiguous.",
        "route_planning_mode": "precomputed",
        "workflow_status": "in_progress",
    }
