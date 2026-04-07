"""Clarification node — asks the user for more information."""

from langgraph.types import interrupt

from app.services.agent.clarification_service import plan_clarification
from app.services.agent_v2.state import AgentState


def _rewrite_question_from_clarification(
    question: str,
    clarification_context: dict[str, str],
) -> tuple[str, list[str], str | None]:
    applied_fields: list[str] = []
    fragments: list[str] = []
    updated_filename: str | None = None

    for key, value in clarification_context.items():
        if not isinstance(value, str):
            continue
        normalized_value = value.strip()
        if not normalized_value:
            continue
        applied_fields.append(key)
        if key in {"filename", "document_scope"}:
            updated_filename = normalized_value
            continue
        fragments.append(f"{key.replace('_', ' ')}: {normalized_value}")

    if not fragments:
        return question, applied_fields, updated_filename

    rewritten_question = f"{question} ({'; '.join(fragments)})"
    return rewritten_question, applied_fields, updated_filename


def clarify_node(state: AgentState) -> dict:
    """
    Request clarification with LangGraph interrupt() and continue once the
    caller resumes execution with structured clarification_context.
    """
    clarification_plan = plan_clarification(state["question"])
    clarification_payload = {
        "clarification_question": clarification_plan.clarification_summary,
        "clarification_plan": clarification_plan.model_dump(),
    }
    clarification_context = interrupt(clarification_payload)
    if not isinstance(clarification_context, dict):
        clarification_context = {}

    rewritten_question, applied_fields, updated_filename = _rewrite_question_from_clarification(
        state["question"],
        clarification_context,
    )
    return {
        "question": rewritten_question,
        "filename": updated_filename or state.get("filename") or "",
        "route": "",
        "route_reason": None,
        "clarification_question": clarification_plan.clarification_summary,
        "clarification_plan": clarification_plan.model_dump(),
        "applied_clarification_fields": applied_fields,
        "question_rewritten": rewritten_question != state["question"],
        "workflow_status": "in_progress",
    }
