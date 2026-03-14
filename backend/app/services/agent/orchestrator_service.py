from app.schemas.query import AgentWorkflowResponse, WorkflowTraceEvent
from app.schemas.tools import ToolExecutionRequest
from app.services.ingestion.document_service import build_utc_timestamp
from app.services.agent.clarification_service import plan_clarification
from app.services.agent.query_service import run_query
from app.services.agent.router_service import route_request
from app.services.agent.tool_service import execute_tool_request, plan_tool_request


def orchestrate_agent_request(
    question: str,
    filename: str | None = None,
    top_k: int = 3,
) -> AgentWorkflowResponse:
    """Route and execute the next workflow step for an agent request."""
    route = route_request(question=question, filename=filename)
    workflow_trace = [
        WorkflowTraceEvent(
            stage="routing",
            status="completed",
            timestamp=build_utc_timestamp(),
            detail=f"Request routed to {route.route_type}.",
        )
    ]

    if route.route_type == "knowledge_retrieval":
        if not filename:
            raise ValueError("filename_required_for_knowledge_route")

        query_response = run_query(
            filename=filename,
            question=question,
            top_k=top_k,
        )
        workflow_trace.extend(
            [
                WorkflowTraceEvent(
                    stage="retrieval",
                    status="completed",
                    timestamp=build_utc_timestamp(),
                    detail=(
                        f"Retrieved {len(query_response.retrieval.matches)} supporting chunks "
                        f"from {query_response.filename}."
                    ),
                ),
                WorkflowTraceEvent(
                    stage="answer_generation",
                    status="completed",
                    timestamp=build_utc_timestamp(),
                    detail=f"Answer generated via {query_response.chat_provider}.",
                ),
            ]
        )
        return AgentWorkflowResponse(
            question=question,
            workflow_status="completed",
            route=route,
            workflow_trace=workflow_trace,
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
        tool_plan = plan_tool_request(question)
        workflow_trace.append(
            WorkflowTraceEvent(
                stage="tool_planning",
                status="completed",
                timestamp=build_utc_timestamp(),
                detail=(
                    f"Planned {tool_plan.tool_name}:{tool_plan.action} for "
                    f"{tool_plan.target}."
                ),
            )
        )
        tool_response = execute_tool_request(
            ToolExecutionRequest(
                tool_name=tool_plan.tool_name,
                action=tool_plan.action,
                target=tool_plan.target,
                arguments=tool_plan.arguments,
            )
        )
        workflow_trace.append(
            WorkflowTraceEvent(
                stage="tool_execution",
                status="completed",
                timestamp=build_utc_timestamp(),
                detail=(
                    f"Executed {tool_response.execution_mode} tool "
                    f"{tool_response.tool_name}:{tool_response.action} "
                    f"with status {tool_response.execution_status}."
                ),
            )
        )
        return AgentWorkflowResponse(
            question=question,
            workflow_status="completed",
            route=route,
            workflow_trace=workflow_trace,
            filename=filename,
            tool_plan=tool_plan.model_dump(),
            tool_execution=tool_response.model_dump(),
        )

    clarification_plan = plan_clarification(question)
    workflow_trace.append(
        WorkflowTraceEvent(
            stage="clarification_planning",
            status="completed",
            timestamp=build_utc_timestamp(),
            detail=(
                f"Clarification requested for fields: "
                f"{', '.join(clarification_plan.missing_fields)}."
            ),
        )
    )
    return AgentWorkflowResponse(
        question=question,
        workflow_status="clarification_required",
        route=route,
        workflow_trace=workflow_trace,
        filename=filename,
        clarification_message=clarification_plan.clarification_summary,
        clarification_plan=clarification_plan.model_dump(),
    )
