from app.services.agent_v2.tracing import finalize_agent_v2_trace
from app.schemas.query import AgentWorkflowResponse, RouteDecision


def test_finalize_agent_v2_trace_ends_and_patches_run_tree():
    captured = {}

    class StubRunTree:
        def end(self, **kwargs):
            captured["end_kwargs"] = kwargs

        def patch(self):
            captured["patched"] = True

    response = AgentWorkflowResponse(
        run_id="run-123",
        question="What is LangGraph?",
        workflow_status="completed",
        terminal_reason="knowledge_answer_generated",
        route=RouteDecision(
            route_type="knowledge_retrieval",
            route_reason="Knowledge question.",
            filename="doc.txt",
        ),
        answer="retrieved answer",
        answer_source="gemini",
        filename="doc.txt",
        started_at="2026-04-07T00:00:00+00:00",
        completed_at="2026-04-07T00:00:00+00:00",
        last_updated_at="2026-04-07T00:00:00+00:00",
    )

    finalize_agent_v2_trace(StubRunTree(), response=response)

    assert captured["end_kwargs"]["outputs"]["run_id"] == "run-123"
    assert captured["end_kwargs"]["outputs"]["route_type"] == "knowledge_retrieval"
    assert captured["end_kwargs"]["metadata"]["workflow_status"] == "completed"
    assert captured["patched"] is True
