"""
AgentState — the single source of truth threaded through the LangGraph graph.

Every node reads from and writes to this TypedDict.  LangGraph persists
snapshots of this state via the AsyncPostgresSaver checkpointer so that
workflows can be resumed or recovered after failures.
"""

from __future__ import annotations

from typing import Annotated, Any
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # ------------------------------------------------------------------ #
    # Input fields (set once at graph entry)                              #
    # ------------------------------------------------------------------ #
    question: str
    filename: str
    top_k: int
    debug_fault_injection: dict[str, Any]
    # Populated by recover_agent_v2_request when action=resume_from_failed_step.
    # Keys: "reuse_tool_chain" (list of pre-completed step dicts), "skip_to_step" (int).
    resume_hints: dict[str, Any]

    # ------------------------------------------------------------------ #
    # Routing                                                             #
    # ------------------------------------------------------------------ #
    # One of: "knowledge_retrieval" | "tool_execution" | "clarification_needed"
    route: str
    route_reason: str | None
    route_planning_mode: str | None
    supervisor_agent: str | None
    supervisor_reason: str | None

    # ------------------------------------------------------------------ #
    # Retrieval                                                           #
    # ------------------------------------------------------------------ #
    retrieval_result: dict[str, Any] | None

    # ------------------------------------------------------------------ #
    # Tool execution                                                      #
    # ------------------------------------------------------------------ #
    # Each entry is a WorkflowStepRecord-compatible dict
    tool_chain: list[dict[str, Any]]

    # ------------------------------------------------------------------ #
    # Clarification                                                       #
    # ------------------------------------------------------------------ #
    clarification_question: str | None
    clarification_plan: dict[str, Any] | None
    applied_clarification_fields: list[str]
    question_rewritten: bool

    # ------------------------------------------------------------------ #
    # Answer                                                              #
    # ------------------------------------------------------------------ #
    answer: str | None
    answer_source: str | None   # "llm" | "fallback" | "tool_result"
    model: str | None
    answered_at: str | None
    answer_latency_ms: float | None
    chat_provider: str | None
    chat_model: str | None

    # ------------------------------------------------------------------ #
    # Workflow metadata                                                   #
    # ------------------------------------------------------------------ #
    # One of: "in_progress" | "completed" | "failed" | "clarification_required"
    workflow_status: str
    terminal_reason_override: str | None
    failure_stage: str | None
    retry_state: str | None
    retry_count: int
    error: str | None

    # ------------------------------------------------------------------ #
    # LangGraph message channel (accumulates, never overwrites)          #
    # ------------------------------------------------------------------ #
    messages: Annotated[list, add_messages]
