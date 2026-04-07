from app.services.llm.route_planner_service import (
    _normalize_route_payload,
    _parse_llm_route_response,
    generate_llm_route_decision,
)


def test_normalize_route_payload_accepts_valid_route():
    payload = {
        "route": "tool_execution",
        "route_reason": "The user is asking to perform an action.",
    }
    normalized = _normalize_route_payload(payload)
    assert normalized == payload


def test_normalize_route_payload_rejects_unknown_route():
    payload = {
        "route": "workflow_execution",
        "route_reason": "Not supported.",
    }
    assert _normalize_route_payload(payload) is None


def test_parse_llm_route_response_strips_fences():
    raw_text = """```json
{"route":"clarification_needed","route_reason":"The target is ambiguous."}
```"""
    parsed = _parse_llm_route_response(raw_text)
    assert parsed == {
        "route": "clarification_needed",
        "route_reason": "The target is ambiguous.",
    }


def test_generate_llm_route_decision_uses_fallback_provider(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm.route_planner_service.settings.route_planner_provider",
        "fallback",
    )
    planning_mode, route = generate_llm_route_decision("What is LangGraph?", "doc.txt")
    assert planning_mode == "heuristic_legacy_router"
    assert route is None


def test_generate_llm_route_decision_returns_cached_route(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm.route_planner_service.settings.route_planner_provider",
        "openai",
    )
    monkeypatch.setattr(
        "app.services.llm.route_planner_service.get_cached_planner_result",
        lambda namespace, payload: {
            "route": "knowledge_retrieval",
            "route_reason": "Cached retrieval route.",
        },
    )
    planning_mode, route = generate_llm_route_decision("What is LangGraph?", "doc.txt")
    assert planning_mode == "llm_openai"
    assert route == {
        "route": "knowledge_retrieval",
        "route_reason": "Cached retrieval route.",
    }


def test_generate_llm_route_decision_handles_provider_errors(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm.route_planner_service.settings.route_planner_provider",
        "openai",
    )
    monkeypatch.setattr(
        "app.services.llm.route_planner_service.settings.openai_api_key",
        "test-key",
    )

    def raise_error(question, filename=None):
        raise ValueError("boom")

    monkeypatch.setattr(
        "app.services.llm.route_planner_service._generate_openai_route_decision",
        raise_error,
    )
    planning_mode, route = generate_llm_route_decision("What is LangGraph?", "doc.txt")
    assert planning_mode == "heuristic_fallback_after_openai_error"
    assert route is None
