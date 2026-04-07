from app.services.agent_v2.nodes.tool_exec import tool_exec_node


BASE_STATE = {
    "question": "Create a ticket for payment-service outage",
    "filename": "",
    "top_k": 3,
    "route": "tool_execution",
    "route_reason": "Tool request.",
    "route_planning_mode": "llm_openai",
    "retrieval_result": None,
    "tool_chain": [],
    "clarification_question": None,
    "answer": None,
    "answer_source": None,
    "workflow_status": "in_progress",
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
