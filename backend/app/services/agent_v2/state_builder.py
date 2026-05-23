from typing import Any


def _build_initial_state(
    question: str,
    filename: str | None,
    top_k: int,
    resume_hints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "question": question,
        "filename": filename or "",
        "top_k": top_k,
        "debug_fault_injection": {},
        "resume_hints": resume_hints or {},
        "route": "",
        "route_reason": None,
        "route_planning_mode": None,
        "supervisor_agent": None,
        "supervisor_reason": None,
        "retrieval_result": None,
        "tool_chain": [],
        "clarification_question": None,
        "clarification_plan": None,
        "applied_clarification_fields": [],
        "question_rewritten": False,
        "answer": None,
        "answer_source": None,
        "model": None,
        "answered_at": None,
        "answer_latency_ms": None,
        "chat_provider": None,
        "chat_model": None,
        "workflow_status": "in_progress",
        "terminal_reason_override": None,
        "failure_stage": None,
        "retry_state": None,
        "retry_count": 0,
        "error": None,
        "messages": [],
    }


def _build_graph_invoke_config(thread_id: str) -> dict[str, dict[str, str]]:
    return {
        "configurable": {
            "thread_id": thread_id,
        }
    }
