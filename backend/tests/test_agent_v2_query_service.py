from langgraph.types import Command

from app.services.agent_v2.query_service import orchestrate_agent_v2_request, stream_agent_v2_request


def test_orchestrate_agent_v2_request_returns_retrieval_response(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: type(
            "Graph",
            (),
            {
                "invoke": lambda self, state, config=None: {
                    **state,
                    "route": "knowledge_retrieval",
                    "route_reason": "Knowledge question.",
                    "route_planning_mode": "llm_openai",
                    "workflow_status": "completed",
                    "answer": "retrieved answer",
                    "answer_source": "fallback",
                    "model": "gemini-2.5-flash",
                    "answered_at": "2026-04-07T00:00:00+00:00",
                    "answer_latency_ms": 123.0,
                    "chat_provider": "gemini",
                    "chat_model": "gemini-2.5-flash",
                    "retrieval_result": {
                        "filename": "doc.txt",
                        "embedding_provider": "gemini",
                        "embedding_model": "gemini-embedding-001",
                        "vector_dim": 3072,
                        "question": "What is LangGraph?",
                        "top_k": 3,
                        "retrieved_at": "2026-04-07T00:00:00+00:00",
                        "retrieval_latency_ms": 50.0,
                        "query_embedding_provider": "gemini",
                        "query_embedding_model": "gemini-embedding-001",
                        "matches": [],
                    },
                },
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
    assert response.retrieval is not None
    assert response.retrieval.filename == "doc.txt"
    assert response.workflow_trace[-1].detail == "retrieved answer"


def test_orchestrate_agent_v2_request_finalizes_langsmith_trace(monkeypatch):
    captured = {}

    class StubTraceContext:
        def __enter__(self):
            captured["entered"] = True
            return "trace-run"

        def __exit__(self, exc_type, exc, tb):
            captured["exited"] = True
            return False

    def stub_trace_agent_v2_run(**kwargs):
        captured["trace_kwargs"] = kwargs
        return StubTraceContext()

    monkeypatch.setattr(
        "app.services.agent_v2.query_service.trace_agent_v2_run",
        stub_trace_agent_v2_run,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.finalize_agent_v2_trace",
        lambda trace_run, *, response=None, error=None: captured.setdefault(
            "finalized",
            {"trace_run": trace_run, "response": response, "error": error},
        ),
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: type(
            "Graph",
            (),
            {
                "invoke": lambda self, state, config=None: {
                    **state,
                    "route": "knowledge_retrieval",
                    "route_reason": "Knowledge question.",
                    "workflow_status": "completed",
                    "answer": "retrieved answer",
                    "answer_source": "fallback",
                    "tool_chain": [],
                },
            },
        )(),
    )

    response = orchestrate_agent_v2_request(question="What is LangGraph?", top_k=3)

    assert captured["trace_kwargs"]["operation"] == "orchestrate"
    assert captured["trace_kwargs"]["inputs"]["question"] == "What is LangGraph?"
    assert captured["finalized"]["trace_run"] == "trace-run"
    assert captured["finalized"]["response"] == response
    assert captured["finalized"]["error"] is None


def test_orchestrate_agent_v2_request_returns_clarification_response(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: type(
            "Graph",
            (),
            {
                "invoke": lambda self, state, config=None: {
                    **state,
                    "route": "clarification_needed",
                    "route_reason": "Ambiguous request.",
                    "route_planning_mode": "heuristic_legacy_router",
                    "__interrupt__": [
                        type(
                            "Interrupt",
                            (),
                            {
                                "value": {
                                    "clarification_question": "Could you clarify your question?",
                                    "clarification_plan": {
                                        "question": "Fix it",
                                        "planning_mode": "heuristic_stub",
                                        "missing_fields": ["task_details"],
                                        "follow_up_questions": ["What exact action should the agent perform?"],
                                        "clarification_summary": "Could you clarify your question?",
                                    },
                                }
                            },
                        )()
                    ],
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
    assert response.clarification_plan is not None
    assert response.terminal_reason == "clarification_requested"
    assert response.recommended_recovery_action == "resume_with_clarification"
    assert response.available_recovery_actions == ["resume_with_clarification"]
    assert response.recovery_action_details == {
        "resume_with_clarification": {
            "missing_fields": ["task_details"],
        }
    }


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
                "answer": "retrieved answer",
                "answer_source": "fallback",
                "model": "gemini-2.5-flash",
                "answered_at": "2026-04-07T00:00:00+00:00",
                "answer_latency_ms": 123.0,
                "chat_provider": "gemini",
                "chat_model": "gemini-2.5-flash",
                "retrieval_result": {
                    "filename": "doc.txt",
                    "embedding_provider": "gemini",
                    "embedding_model": "gemini-embedding-001",
                    "vector_dim": 3072,
                    "question": "What is LangGraph?",
                    "top_k": 3,
                    "retrieved_at": "2026-04-07T00:00:00+00:00",
                    "retrieval_latency_ms": 50.0,
                    "query_embedding_provider": "gemini",
                    "query_embedding_model": "gemini-embedding-001",
                    "matches": [],
                },
            }

    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: StubGraph(),
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )
    response = orchestrate_agent_v2_request(
        question="What is LangGraph?",
        filename="doc.txt",
        top_k=3,
        checkpointer=object(),
    )
    assert response.run_id
    assert captured["config"]["configurable"]["thread_id"] == response.run_id


def test_orchestrate_agent_v2_request_returns_tool_result(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: type(
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


def test_stream_agent_v2_request_emits_updates_and_final_result(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.trace_agent_v2_run",
        lambda **kwargs: type(
            "TraceContext",
            (),
            {
                "__enter__": lambda self: "stream-trace",
                "__exit__": lambda self, exc_type, exc, tb: False,
            },
        )(),
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.finalize_agent_v2_trace",
        lambda trace_run, *, response=None, error=None: None,
    )

    class StubGraph:
        def stream(self, state, config=None, stream_mode=None):
            assert stream_mode == "updates"
            yield {
                "router": {
                    "route": "tool_execution",
                    "route_reason": "Execution request.",
                    "route_planning_mode": "llm_openai",
                    "workflow_status": "in_progress",
                }
            }
            yield {
                "supervisor": {
                    "supervisor_agent": "operations_specialist",
                    "supervisor_reason": "Supervisor delegated tool_execution to operations_specialist based on the current route decision.",
                    "workflow_status": "in_progress",
                }
            }
            yield {
                "operations_specialist": {
                    "tool_chain": [
                        {
                            "step_id": "step_1",
                            "step_index": 1,
                            "step_status": "completed",
                            "attempt_count": 1,
                            "retried": False,
                            "started_at": "2026-04-07T00:00:00+00:00",
                            "completed_at": "2026-04-07T00:00:01+00:00",
                            "question": "Create a ticket",
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
                    "answer": "Created ticket TICKET-0001 for payment-service.",
                    "answer_source": "tool_result",
                    "workflow_status": "completed",
                }
            }
            yield {
                "answer": {
                    "answer": "Created ticket TICKET-0001 for payment-service.",
                    "answer_source": "tool_result",
                    "workflow_status": "completed",
                }
            }

    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: StubGraph(),
    )

    events = list(
        stream_agent_v2_request(
            question="Create a ticket",
            filename=None,
            top_k=3,
        )
    )

    assert events[0]["stage"] == "start"
    assert events[1]["stage"] == "routing"
    assert events[2]["stage"] == "supervisor"
    assert events[3]["stage"] == "operations_specialist"
    assert events[-2]["stage"] == "workflow"
    assert events[-1]["event_type"] == "result"
    assert events[-1]["response"]["answer"] == "Created ticket TICKET-0001 for payment-service."


def test_resume_agent_v2_request_rehydrates_from_checkpoint(monkeypatch):
    from app.schemas.query import RouteDecision, AgentWorkflowResponse
    from app.services.agent_v2.query_service import resume_agent_v2_request

    persisted_run = AgentWorkflowResponse(
        run_id="run-123",
        question="What is LangGraph?",
        workflow_status="completed",
        route=RouteDecision(
            route_type="knowledge_retrieval",
            route_reason="Knowledge question.",
            filename="doc.txt",
        ),
        answer="old answer",
        answer_source="fallback",
        model="gemini-2.5-flash",
        answered_at="2026-04-07T00:00:00+00:00",
        answer_latency_ms=123.0,
        chat_provider="gemini",
        chat_model="gemini-2.5-flash",
        filename="doc.txt",
        started_at="2026-04-07T00:00:00+00:00",
        completed_at="2026-04-07T00:00:00+00:00",
        last_updated_at="2026-04-07T00:00:00+00:00",
    )

    class StubSnapshot:
        values = {
            "question": "What is LangGraph?",
            "filename": "doc.txt",
            "route": "knowledge_retrieval",
            "route_reason": "Knowledge question.",
            "workflow_status": "completed",
            "answer": "resumed answer",
            "answer_source": "fallback",
            "model": "gemini-2.5-flash",
            "answered_at": "2026-04-07T00:00:01+00:00",
            "answer_latency_ms": 99.0,
            "chat_provider": "gemini",
            "chat_model": "gemini-2.5-flash",
            "retrieval_result": None,
            "tool_chain": [],
        }

    class StubGraph:
        def get_state(self, config):
            return StubSnapshot()

        def invoke(self, payload, config=None):
            assert payload is None
            return dict(StubSnapshot.values)

    monkeypatch.setattr(
        "app.services.agent_v2.query_service.get_persisted_agent_v2_run",
        lambda run_id: persisted_run,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: StubGraph(),
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )

    response = resume_agent_v2_request(run_id="run-123", checkpointer=object())
    assert response.run_id == "run-123"
    assert response.resume_source_type == "run_id"
    assert response.resume_strategy == "checkpoint_resume"
    assert response.answer == "resumed answer"
    assert response.completed_at == "2026-04-07T00:00:00+00:00"


def test_resume_agent_v2_request_sets_completed_at_when_source_run_was_incomplete(monkeypatch):
    from app.schemas.query import RouteDecision, AgentWorkflowResponse
    from app.services.agent_v2.query_service import resume_agent_v2_request

    persisted_run = AgentWorkflowResponse(
        run_id="run-456",
        question="What is LangGraph?",
        workflow_status="in_progress",
        route=RouteDecision(
            route_type="knowledge_retrieval",
            route_reason="Knowledge question.",
            filename="doc.txt",
        ),
        answer=None,
        answer_source=None,
        filename="doc.txt",
        started_at="2026-04-07T00:00:00+00:00",
        completed_at=None,
        last_updated_at="2026-04-07T00:00:00+00:00",
    )

    class StubSnapshot:
        values = {
            "question": "What is LangGraph?",
            "filename": "doc.txt",
        }

    class StubGraph:
        def get_state(self, config):
            return StubSnapshot()

        def invoke(self, payload, config=None):
            assert payload is None
            return {
                "question": "What is LangGraph?",
                "filename": "doc.txt",
                "route": "knowledge_retrieval",
                "route_reason": "Knowledge question.",
                "workflow_status": "completed",
                "answer": "resumed answer",
                "answer_source": "fallback",
                "tool_chain": [],
            }

    monkeypatch.setattr(
        "app.services.agent_v2.query_service.get_persisted_agent_v2_run",
        lambda run_id: persisted_run,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: StubGraph(),
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_utc_timestamp",
        lambda: "2026-04-07T00:05:00+00:00",
    )

    response = resume_agent_v2_request(run_id="run-456", checkpointer=object())
    assert response.completed_at == "2026-04-07T00:05:00+00:00"
    assert response.last_updated_at == "2026-04-07T00:05:00+00:00"


def test_resume_agent_v2_request_uses_command_resume_for_clarification(monkeypatch):
    from app.schemas.query import RouteDecision, AgentWorkflowResponse
    from app.services.agent_v2.query_service import resume_agent_v2_request

    persisted_run = AgentWorkflowResponse(
        run_id="run-789",
        question="Fix it",
        workflow_status="clarification_required",
        route=RouteDecision(
            route_type="clarification_needed",
            route_reason="Ambiguous request.",
            filename=None,
        ),
        clarification_message="Could you clarify your question?",
        clarification_plan={
            "question": "Fix it",
            "planning_mode": "heuristic_stub",
            "missing_fields": ["task_details"],
            "follow_up_questions": ["What exact action should the agent perform?"],
            "clarification_summary": "Could you clarify your question?",
        },
        started_at="2026-04-07T00:00:00+00:00",
        last_updated_at="2026-04-07T00:00:00+00:00",
    )
    captured = {}

    class StubSnapshot:
        values = {"question": "Fix it"}

    class StubGraph:
        def get_state(self, config):
            return StubSnapshot()

        def invoke(self, payload, config=None):
            captured["payload"] = payload
            return {
                "question": "Fix it (environment: production)",
                "filename": "",
                "route": "knowledge_retrieval",
                "route_reason": "Now specific enough.",
                "workflow_status": "completed",
                "answer": "resolved answer",
                "answer_source": "fallback",
                "applied_clarification_fields": ["environment"],
                "question_rewritten": True,
                "tool_chain": [],
            }

    monkeypatch.setattr(
        "app.services.agent_v2.query_service.get_persisted_agent_v2_run",
        lambda run_id: persisted_run,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: StubGraph(),
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )

    response = resume_agent_v2_request(
        run_id="run-789",
        clarification_context={"environment": "production"},
        checkpointer=object(),
    )
    assert isinstance(captured["payload"], Command)
    assert captured["payload"].resume == {"environment": "production"}
    assert response.answer == "resolved answer"
    assert response.applied_clarification_fields == ["environment"]
    assert response.question_rewritten is True
    assert response.recommended_recovery_action == "none"
    assert response.available_recovery_actions == []


def test_resume_agent_v2_request_finalizes_langsmith_trace(monkeypatch):
    from app.schemas.query import RouteDecision, AgentWorkflowResponse
    from app.services.agent_v2.query_service import resume_agent_v2_request

    persisted_run = AgentWorkflowResponse(
        run_id="run-trace",
        question="Fix it",
        workflow_status="clarification_required",
        route=RouteDecision(
            route_type="clarification_needed",
            route_reason="Ambiguous request.",
            filename=None,
        ),
        clarification_message="Could you clarify your question?",
        started_at="2026-04-07T00:00:00+00:00",
        last_updated_at="2026-04-07T00:00:00+00:00",
    )
    captured = {}

    class StubSnapshot:
        values = {"question": "Fix it"}

    class StubTraceContext:
        def __enter__(self):
            return "resume-trace"

        def __exit__(self, exc_type, exc, tb):
            return False

    def stub_trace_agent_v2_run(**kwargs):
        captured["trace_kwargs"] = kwargs
        return StubTraceContext()

    class StubGraph:
        def get_state(self, config):
            return StubSnapshot()

        def invoke(self, payload, config=None):
            return {
                "question": "Fix it (environment: production)",
                "route": "tool_execution",
                "route_reason": "Specific enough.",
                "workflow_status": "completed",
                "answer": "resolved answer",
                "answer_source": "tool_result",
                "tool_chain": [],
            }

    monkeypatch.setattr(
        "app.services.agent_v2.query_service.get_persisted_agent_v2_run",
        lambda run_id: persisted_run,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.build_graph",
        lambda checkpointer=None: StubGraph(),
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.trace_agent_v2_run",
        stub_trace_agent_v2_run,
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.finalize_agent_v2_trace",
        lambda trace_run, *, response=None, error=None: captured.setdefault(
            "finalized",
            {"trace_run": trace_run, "response": response, "error": error},
        ),
    )
    monkeypatch.setattr(
        "app.services.agent_v2.query_service.persist_agent_v2_run",
        lambda response: None,
    )

    response = resume_agent_v2_request(
        run_id="run-trace",
        clarification_context={"environment": "production"},
        checkpointer=object(),
    )

    assert captured["trace_kwargs"]["operation"] == "resume"
    assert captured["trace_kwargs"]["inputs"]["run_id"] == "run-trace"
    assert captured["trace_kwargs"]["inputs"]["clarification_context_keys"] == ["environment"]
    assert captured["finalized"]["trace_run"] == "resume-trace"
    assert captured["finalized"]["response"] == response
    assert captured["finalized"]["error"] is None
