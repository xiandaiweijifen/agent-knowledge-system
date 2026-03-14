from app.schemas.query import AgentWorkflowResponse
from app.schemas.tools import ToolExecutionRequest
from app.services.agent.query_service import run_query
from app.services.agent.router_service import route_request
from app.services.agent.tool_service import execute_tool_request, infer_tool_request


def orchestrate_agent_request(
    question: str,
    filename: str | None = None,
    top_k: int = 3,
) -> AgentWorkflowResponse:
    """Route and execute the next workflow step for an agent request."""
    route = route_request(question=question, filename=filename)

    if route.route_type == "knowledge_retrieval":
        if not filename:
            raise ValueError("filename_required_for_knowledge_route")

        query_response = run_query(
            filename=filename,
            question=question,
            top_k=top_k,
        )
        return AgentWorkflowResponse(
            question=question,
            workflow_status="completed",
            route=route,
            filename=query_response.filename,
            answer=query_response.answer,
            answer_source=query_response.answer_source,
            model=query_response.model,
            answered_at=query_response.answered_at,
            answer_latency_ms=query_response.answer_latency_ms,
            chat_provider=query_response.chat_provider,
            chat_model=query_response.chat_model,
            retrieval=query_response.retrieval,
        )

    if route.route_type == "tool_execution":
        inferred_tool_request = infer_tool_request(question)
        tool_response = execute_tool_request(
            ToolExecutionRequest(
                tool_name=inferred_tool_request.tool_name,
                action=inferred_tool_request.action,
                target=inferred_tool_request.target,
            )
        )
        return AgentWorkflowResponse(
            question=question,
            workflow_status="completed",
            route=route,
            filename=filename,
            tool_execution=tool_response.model_dump(),
        )

    return AgentWorkflowResponse(
        question=question,
        workflow_status="clarification_required",
        route=route,
        filename=filename,
        clarification_message=(
            "The request is underspecified. Clarify the target, environment, or action "
            "before the agent proceeds."
        ),
    )
