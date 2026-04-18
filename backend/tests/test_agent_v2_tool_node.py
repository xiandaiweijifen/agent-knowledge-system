from app.services.agent_v2.nodes.tool_exec import tool_exec_node


BASE_STATE = {
    "question": "Create a ticket for payment-service outage",
    "filename": "",
    "top_k": 3,
    "debug_fault_injection": {},
    "route": "tool_execution",
    "route_reason": "Tool request.",
    "route_planning_mode": "llm_openai",
    "retrieval_result": None,
    "tool_chain": [],
    "clarification_question": None,
    "clarification_plan": None,
    "applied_clarification_fields": [],
    "question_rewritten": False,
    "answer": None,
    "answer_source": None,
    "workflow_status": "in_progress",
    "failure_stage": None,
    "retry_state": None,
    "retry_count": 0,
    "error": None,
    "messages": [],
}


def test_tool_exec_node_uses_existing_tool_services(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_v2.nodes.tool_exec.build_utc_timestamp",
        lambda: "2026-04-07T00:00:00+00:00",
    )
    monkeypatch.setattr(
        "app.services.agent_v2.nodes.tool_exec.plan_tool_request",
        lambda question: type(
            "ToolPlan",
            (),
            {
                "tool_name": "ticketing",
                "action": "create",
                "target": "payment-service",
                "arguments": {"severity": "high"},
                "model_dump": lambda self=None: {
                    "tool_name": "ticketing",
                    "action": "create",
                    "target": "payment-service",
                    "arguments": {"severity": "high"},
                    "planning_mode": "heuristic_stub",
                },
            },
        )(),
    )
    monkeypatch.setattr(
        "app.services.agent_v2.nodes.tool_exec.execute_tool_request",
        lambda request: type(
            "ToolExecution",
            (),
            {
                "execution_status": "completed",
                "executed_at": "2026-04-07T00:00:01+00:00",
                "result_summary": "Created ticket TICKET-0001 for payment-service.",
                "model_dump": lambda self=None: {
                    "tool_name": "ticketing",
                    "action": "create",
                    "target": "payment-service",
                    "execution_status": "completed",
                    "execution_mode": "local_adapter",
                    "result_summary": "Created ticket TICKET-0001 for payment-service.",
                    "trace_id": "trace-1",
                    "executed_at": "2026-04-07T00:00:01+00:00",
                    "output": {"ticket_id": "TICKET-0001"},
                },
            },
        )(),
    )
    result = tool_exec_node(BASE_STATE)
    assert result["workflow_status"] == "completed"
    assert result["answer_source"] == "tool_result"
    assert result["answer"] == "Created ticket TICKET-0001 for payment-service."
    assert len(result["tool_chain"]) == 1
    assert result["tool_chain"][0]["tool_plan"]["tool_name"] == "ticketing"
    assert result["tool_chain"][0]["started_at"] <= result["tool_chain"][0]["completed_at"]


def test_tool_exec_node_returns_failed_state_for_injected_failure(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_v2.nodes.tool_exec.build_utc_timestamp",
        lambda: "2026-04-07T00:00:00+00:00",
    )
    monkeypatch.setattr(
        "app.services.agent_v2.nodes.tool_exec.plan_tool_request",
        lambda question: type(
            "ToolPlan",
            (),
            {
                "tool_name": "ticketing",
                "action": "create",
                "target": "payment-service",
                "arguments": {"severity": "high"},
                "model_dump": lambda self=None: {
                    "tool_name": "ticketing",
                    "action": "create",
                    "target": "payment-service",
                    "arguments": {"severity": "high"},
                },
            },
        )(),
    )
    result = tool_exec_node(
        {
            **BASE_STATE,
            "debug_fault_injection": {
                "tool_execution_failures": [
                    {
                        "tool_name": "ticketing",
                        "action": "create",
                        "fail_count": 1,
                        "message": "debug injected persistent failure",
                    }
                ]
            },
        }
    )
    assert result["workflow_status"] == "failed"
    assert result["failure_stage"] == "tool_execution"
    assert result["retry_state"] == "retry_exhausted"
    assert result["retry_count"] == 1
    assert result["error"] == "debug injected persistent failure"
    assert result["tool_chain"][0]["step_status"] == "failed"


def test_tool_exec_node_runs_incident_triage_workflow(monkeypatch):
    def _build_execution(*, tool_name, action, target, output, summary):
        return type(
            "ToolExecution",
            (),
            {
                "tool_name": tool_name,
                "action": action,
                "target": target,
                "execution_status": "completed",
                "executed_at": "2026-04-07T00:00:01+00:00",
                "result_summary": summary,
                "model_dump": lambda self=None: {
                    "tool_name": tool_name,
                    "action": action,
                    "target": target,
                    "execution_status": "completed",
                    "execution_mode": "local_adapter",
                    "result_summary": summary,
                    "trace_id": f"{tool_name}-{action}",
                    "executed_at": "2026-04-07T00:00:01+00:00",
                    "output": output,
                },
            },
        )()

    def _execute(request):
        if request.tool_name == "system_status":
            return _build_execution(
                tool_name="system_status",
                action="query",
                target=request.target,
                summary="Collected local system status for payment-service with requested environment production.",
                output={
                    "health": "degraded",
                    "summary": "Service is degraded due to elevated timeout rate and downstream DB latency.",
                    "service_record": {
                        "runbook_doc_ids": ["payment_service_runbook.md", "incident_playbook.md"],
                    },
                },
            )
        if request.tool_name == "document_search":
            assert request.arguments["filename"] == "payment_service_runbook.md"
            assert request.target == "timeout"
            return _build_execution(
                tool_name="document_search",
                action="query",
                target=request.target,
                summary="Found 2 supporting documents for payment-service timeout.",
                output={
                    "matched_documents": "payment_service_runbook.md, incident_playbook.md",
                },
            )
        return _build_execution(
            tool_name="ticketing",
            action="draft",
            target=request.target,
            summary="Prepared ticket draft TICKET-0001 for payment-service.",
            output={
                "ticket_id": "TICKET-0001",
                "status": "draft",
                "submission_state": "awaiting_user_confirmation",
            },
        )

    monkeypatch.setattr("app.services.agent_v2.nodes.tool_exec.execute_tool_request", _execute)

    result = tool_exec_node(
        {
            **BASE_STATE,
            "question": "Check payment-service in production for timeout issues and if it is abnormal prepare a high severity ticket draft",
        }
    )

    assert result["workflow_status"] == "clarification_required"
    assert result["clarification_plan"]["confirmation_kind"] == "ticket_submission"
    assert result["clarification_plan"]["ticket_id"] == "TICKET-0001"
    assert result["answer_source"] == "local_incident_triage"
    assert len(result["tool_chain"]) == 3
    assert result["tool_chain"][0]["tool_plan"]["tool_name"] == "system_status"
    assert result["tool_chain"][1]["tool_plan"]["tool_name"] == "document_search"
    assert result["tool_chain"][2]["tool_plan"]["tool_name"] == "ticketing"
    assert result["tool_chain"][2]["tool_plan"]["action"] == "draft"
