from typing import Any


def _extract_interrupt_payload(final_state: dict[str, Any]) -> dict[str, Any] | None:
    interrupts = final_state.get("__interrupt__")
    if not isinstance(interrupts, (list, tuple)) or not interrupts:
        return None

    interrupt_event = interrupts[0]
    payload = getattr(interrupt_event, "value", None)
    return payload if isinstance(payload, dict) else None


def _collect_tool_payload(
    final_state: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[dict[str, Any]]]:
    tool_execution = None
    tool_plan = None
    tool_chain = final_state.get("tool_chain") or []
    if tool_chain:
        last_step = tool_chain[-1]
        if isinstance(last_step, dict):
            tool_plan = last_step.get("tool_plan")
            tool_execution = last_step.get("tool_execution")
    return tool_plan, tool_execution, tool_chain


def _extract_step_output(tool_chain: list[dict[str, Any]], tool_name: str) -> dict[str, Any]:
    for step in tool_chain:
        if not isinstance(step, dict):
            continue
        tool_plan = step.get("tool_plan") or {}
        if str(tool_plan.get("tool_name") or "").strip().lower() != tool_name:
            continue
        output = (step.get("tool_execution") or {}).get("output") or {}
        if isinstance(output, dict):
            return output
    return {}
