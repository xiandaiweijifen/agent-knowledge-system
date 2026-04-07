from app.services.agent_v2.query_service import orchestrate_agent_v2_request


def test_orchestrate_agent_v2_request_returns_retrieval_response(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.agent_graph",
        type(
            "Graph",
            (),
            {
                "invoke": lambda self, state, config=None: {
                    **state,
                    "route": "knowledge_retrieval",
                    "route_reason": "Knowledge question.",
                    "route_planning_mode": "llm_openai",
                    "workflow_status": "completed",
                    "answer": "stub answer",
                    "answer_source": "stub",
                },
            },
        )(),
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.run_query",
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
                "retrieval": None,
            },
        )(),
    )
    response = orchestrate_agent_v2_request(
        question="What is LangGraph?",
        filename="doc.txt",
        top_k=3,
    )
    assert response.route.route_type == "knowledge_retrieval"
    assert response.answer == "retrieved answer"
    assert response.workflow_planning_mode == "llm_openai"
    assert response.model == "gemini-2.5-flash"
    assert response.chat_provider == "gemini"
    assert response.chat_model == "gemini-2.5-flash"
    assert response.answer_latency_ms == 123.0
    assert response.answered_at == "2026-04-07T00:00:00+00:00"
    assert response.workflow_trace[-1].detail == "retrieved answer"


def test_orchestrate_agent_v2_request_returns_clarification_response(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.agent_graph",
        type(
            "Graph",
            (),
            {
                "invoke": lambda self, state, config=None: {
                    **state,
                    "route": "clarification_needed",
                    "route_reason": "Ambiguous request.",
                    "route_planning_mode": "heuristic_legacy_router",
                    "workflow_status": "clarification_required",
                    "clarification_question": "Could you clarify your question?",
                },
            },
        )(),
    )
    response = orchestrate_agent_v2_request(
        question="Fix it",
        filename=None,
        top_k=3,
    )
    assert response.workflow_status == "clarification_required"
    assert response.clarification_message == "Could you clarify your question?"
    assert response.terminal_reason == "clarification_requested"


def test_orchestrate_agent_v2_request_passes_thread_config_when_checkpointer_present(monkeypatch):
    captured = {}

    class StubGraph:
        def invoke(self, state, config=None):
            captured["config"] = config
            return {
                **state,
                "route": "knowledge_retrieval",
                "route_reason": "Knowledge question.",
                "route_planning_mode": "llm_openai",
                "workflow_status": "completed",
                "answer": "stub answer",
                "answer_source": "stub",
            }

    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: StubGraph(),
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.run_query",
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
                "retrieval": None,
            },
        )(),
    )
    response = orchestrate_agent_v2_request(
        question="What is LangGraph?",
        filename="doc.txt",
        top_k=3,
        checkpointer=object(),
    )
    assert response.run_id
    assert captured["config"]["configurable"]["thread_id"] == response.run_id
    assert captured["config"]["configurable"]["checkpoint_ns"] == "agent_v2"


def test_orchestrate_agent_v2_request_returns_tool_result(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.agent_graph",
        type(
            "Graph",
            (),
            {
                "invoke": lambda self, state, config=None: {
                    **state,
                    "route": "tool_execution",
                    "route_reason": "Execution request.",
                    "route_planning_mode": "llm_openai",
                    "workflow_status": "completed",
                    "answer": "Created ticket TICKET-0001 for payment-service.",
                    "answer_source": "tool_result",
                    "tool_chain": [
                        {
                            "step_id": "step_1",
                            "step_index": 1,
                            "step_status": "completed",
                            "attempt_count": 1,
                            "retried": False,
                            "started_at": "2026-04-07T00:00:00+00:00",
                            "completed_at": "2026-04-07T00:00:00+00:00",
                            "question": "Create a ticket for payment-service outage",
                            "tool_plan": {
                                "tool_name": "ticketing",
                                "action": "create",
                                "target": "payment-service",
                                "arguments": {"severity": "high"},
                            },
                            "tool_execution": {
                                "tool_name": "ticketing",
                                "action": "create",
                                "target": "payment-service",
                                "execution_status": "completed",
                                "result_summary": "Created ticket TICKET-0001 for payment-service.",
                            },
                        }
                    ],
                },
            },
        )(),
    )
    response = orchestrate_agent_v2_request(
        question="Create a ticket for payment-service outage",
        filename=None,
        top_k=3,
    )
    assert response.route.route_type == "tool_execution"
    assert response.answer == "Created ticket TICKET-0001 for payment-service."
    assert response.answer_source == "tool_result"
    assert response.tool_plan["tool_name"] == "ticketing"
    assert response.tool_execution["execution_status"] == "completed"
    assert response.workflow_trace[-1].detail == "Tool execution node completed in agent_v2."
