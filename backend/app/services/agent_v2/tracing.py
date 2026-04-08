import os
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

from langsmith import Client, trace
from langsmith.run_trees import RunTree

from app.core.config import settings
from app.schemas.query import AgentWorkflowResponse


def is_langsmith_tracing_enabled() -> bool:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return settings.langsmith_tracing_enabled and bool(settings.langsmith_api_key.strip())


@lru_cache(maxsize=1)
def get_langsmith_client() -> Client | None:
    if not is_langsmith_tracing_enabled():
        return None

    return Client(
        api_key=settings.langsmith_api_key,
        api_url=settings.langsmith_endpoint or None,
    )


@contextmanager
def trace_agent_v2_run(
    *,
    operation: str,
    inputs: dict[str, Any],
    metadata: dict[str, Any],
):
    if not is_langsmith_tracing_enabled():
        yield None
        return

    client = get_langsmith_client()
    with trace(
        name=f"agent_v2.{operation}",
        run_type="chain",
        inputs=inputs,
        project_name=settings.langsmith_project,
        tags=["agent_v2", operation],
        metadata=metadata,
        client=client,
    ) as run_tree:
        yield run_tree


def finalize_agent_v2_trace(
    run_tree: RunTree | None,
    *,
    response: AgentWorkflowResponse | None = None,
    error: Exception | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    if run_tree is None:
        return

    final_metadata = dict(metadata or {})
    outputs = None

    if response is not None:
        final_metadata.update(
            {
                "workflow_status": response.workflow_status,
                "terminal_reason": response.terminal_reason,
                "route_type": response.route.route_type,
                "answer_source": response.answer_source,
                "tool_name": (response.tool_plan or {}).get("tool_name"),
                "retrieved_match_count": len(response.retrieval.matches) if response.retrieval else 0,
            }
        )
        outputs = {
            "run_id": response.run_id,
            "question": response.question,
            "workflow_status": response.workflow_status,
            "terminal_reason": response.terminal_reason,
            "route_type": response.route.route_type,
            "route_reason": response.route.route_reason,
            "answer": response.answer,
            "answer_source": response.answer_source,
            "filename": response.filename,
            "tool_execution_status": (response.tool_execution or {}).get("execution_status"),
            "tool_name": (response.tool_plan or {}).get("tool_name"),
            "retrieved_match_count": len(response.retrieval.matches) if response.retrieval else 0,
        }

    run_tree.end(
        outputs=outputs,
        error=str(error) if error else None,
        metadata=final_metadata or None,
    )
    run_tree.patch()
