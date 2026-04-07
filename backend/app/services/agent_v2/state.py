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

    # ------------------------------------------------------------------ #
    # Routing                                                             #
    # ------------------------------------------------------------------ #
    # One of: "knowledge_retrieval" | "tool_execution" | "clarification_needed"
    route: str

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

    # ------------------------------------------------------------------ #
    # Answer                                                              #
    # ------------------------------------------------------------------ #
    answer: str | None
    answer_source: str | None   # "llm" | "fallback" | "tool_result"

    # ------------------------------------------------------------------ #
    # Workflow metadata                                                   #
    # ------------------------------------------------------------------ #
    # One of: "in_progress" | "completed" | "failed" | "clarification_required"
    workflow_status: str
    error: str | None

    # ------------------------------------------------------------------ #
    # LangGraph message channel (accumulates, never overwrites)          #
    # ------------------------------------------------------------------ #
    messages: Annotated[list, add_messages]
