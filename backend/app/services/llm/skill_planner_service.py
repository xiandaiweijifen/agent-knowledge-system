"""LLM-backed skill planner — selects which workflow skill to execute for a tool-execution request."""

import json

import httpx

from app.core.config import settings
from app.services.llm.planner_cache_service import (
    get_cached_planner_result,
    set_cached_planner_result,
)


OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_GENERATE_CONTENT_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/{model_name}:generateContent"
)

# Workflow skills the planner can select. "single_tool" means fall through to the
# default single-step LLM tool plan — not a named workflow.
SUPPORTED_SKILL_IDS = {"incident_triage", "service_runtime_review", "single_tool"}

_WORKFLOW_SKILL_DESCRIPTIONS = {
    "incident_triage": (
        "Incident Triage",
        "Multi-step workflow: checks service health, collects runbook and external evidence, "
        "then prepares a ticket draft and waits for operator confirmation before submitting.",
    ),
    "service_runtime_review": (
        "Service Runtime Review",
        "Multi-step workflow: checks service health, inspects downstream dependencies, "
        "and retrieves runbook guidance to recommend what the operator should look at next.",
    ),
    "single_tool": (
        "Single Tool Execution",
        "A single operational tool call — for requests that do not require incident triage "
        "or service runtime review (e.g. create a ticket directly, search documents, check status).",
    ),
}


def _resolve_openai_skill_planner_model() -> str:
    return settings.openai_skill_planner_model.strip() or settings.openai_chat_model


def _resolve_gemini_skill_planner_model() -> str:
    return settings.gemini_skill_planner_model.strip() or settings.gemini_chat_model


def _strip_json_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```JSON").removeprefix("```")
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    return cleaned.strip()


def _build_skill_options_text() -> str:
    lines = []
    for skill_id in ("incident_triage", "service_runtime_review", "single_tool"):
        label, description = _WORKFLOW_SKILL_DESCRIPTIONS[skill_id]
        lines.append(f'- "{skill_id}" ({label}): {description}')
    return "\n".join(lines)


def _build_skill_planner_prompt(question: str) -> str:
    options = _build_skill_options_text()
    return (
        "You are a skill dispatcher for an engineering agent. "
        "Select exactly one skill_id that best handles the user request.\n\n"
        f"Available skills:\n{options}\n\n"
        f"User request: {question}"
    )


def _normalize_skill_payload(payload: dict) -> dict[str, str] | None:
    skill_id = payload.get("skill_id")
    if not isinstance(skill_id, str):
        return None
    normalized = skill_id.strip().lower()
    if normalized not in SUPPORTED_SKILL_IDS:
        return None
    reasoning = str(payload.get("reasoning") or "").strip()
    return {"skill_id": normalized, "reasoning": reasoning}


def _parse_llm_skill_response(raw_text: str) -> dict[str, str] | None:
    cleaned = _strip_json_fences(raw_text)
    if not cleaned:
        return None
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return _normalize_skill_payload(payload)


def _extract_openai_tool_call_arguments(payload: dict) -> str | None:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    message = choices[0].get("message", {})
    if not isinstance(message, dict):
        return None
    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list) and tool_calls:
        first = tool_calls[0]
        if isinstance(first, dict):
            fn = first.get("function", {})
            if isinstance(fn, dict):
                arguments = fn.get("arguments")
                if isinstance(arguments, str):
                    return arguments
    content = message.get("content")
    return content if isinstance(content, str) else None


def _generate_openai_skill_decision(question: str) -> dict[str, str] | None:
    model_name = _resolve_openai_skill_planner_model()
    response = httpx.post(
        OPENAI_CHAT_COMPLETIONS_URL,
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model_name,
            "temperature": 0,
            "tool_choice": {"type": "function", "function": {"name": "select_skill"}},
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "select_skill",
                        "description": "Select the best skill for the user request.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "skill_id": {
                                    "type": "string",
                                    "enum": sorted(SUPPORTED_SKILL_IDS),
                                },
                                "reasoning": {"type": "string"},
                            },
                            "required": ["skill_id", "reasoning"],
                            "additionalProperties": False,
                        },
                    },
                }
            ],
            "messages": [
                {
                    "role": "system",
                    "content": "Use the provided tool to return the skill selection.",
                },
                {
                    "role": "user",
                    "content": _build_skill_planner_prompt(question),
                },
            ],
        },
        timeout=30.0,
    )
    response.raise_for_status()
    arguments = _extract_openai_tool_call_arguments(response.json())
    if not isinstance(arguments, str):
        return None
    return _parse_llm_skill_response(arguments)


def _extract_text_from_candidate_payload(payload) -> list[str]:
    texts: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == "text" and isinstance(value, str) and value.strip():
                texts.append(value)
            else:
                texts.extend(_extract_text_from_candidate_payload(value))
    elif isinstance(payload, list):
        for item in payload:
            texts.extend(_extract_text_from_candidate_payload(item))
    return texts


def _generate_gemini_skill_decision(question: str) -> dict[str, str] | None:
    model_name = _resolve_gemini_skill_planner_model()
    response = httpx.post(
        GEMINI_GENERATE_CONTENT_URL_TEMPLATE.format(model_name=model_name),
        headers={
            "x-goog-api-key": settings.gemini_api_key,
            "Content-Type": "application/json",
        },
        json={
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                _build_skill_planner_prompt(question)
                                + "\n\nReturn JSON only with keys: skill_id, reasoning."
                            ),
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        },
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return None
    texts: list[str] = []
    for candidate in candidates:
        texts.extend(_extract_text_from_candidate_payload(candidate))
    if not texts:
        return None
    return _parse_llm_skill_response("\n".join(texts).strip())


def _heuristic_skill_dispatch(question: str) -> str | None:
    """Keyword-based fallback when LLM skill planner is unavailable or disabled."""
    words = set(question.lower().split())

    # "triage" alone is a strong unambiguous signal for incident triage.
    if "triage" in words:
        return "incident_triage"

    incident_signal = words & {"ticket", "draft", "incident", "outage", "alert", "abnormal"}
    action_signal = words & {"check", "inspect", "investigate", "review"}
    runtime_signal = words & {"status", "health", "runtime", "running", "degraded", "healthy"}

    # Incident triage: action + ticket/incident intent together.
    if incident_signal and action_signal:
        return "incident_triage"
    # Service runtime review: status/health check without ticket intent.
    if runtime_signal and action_signal:
        return "service_runtime_review"
    return None


def generate_llm_skill_decision(question: str) -> tuple[str, dict[str, str] | None]:
    """Select the best workflow skill for a tool-execution request.

    Returns (planning_mode, skill_payload) where skill_payload has keys
    "skill_id" and "reasoning", or None when falling back to heuristic.
    skill_id values: "incident_triage" | "service_runtime_review" | "single_tool".
    """
    provider = settings.skill_planner_provider.lower().strip()

    if provider == "fallback":
        heuristic_id = _heuristic_skill_dispatch(question)
        if heuristic_id is None:
            return "heuristic_fallback", None
        return "heuristic_fallback", {"skill_id": heuristic_id, "reasoning": "heuristic keyword match"}

    cache_payload = {"provider": provider, "question": question}
    cached = get_cached_planner_result("skill_planner", cache_payload)
    if cached is not None:
        return f"llm_{provider}", cached

    try:
        if provider == "openai":
            if not settings.openai_api_key:
                heuristic_id = _heuristic_skill_dispatch(question)
                return "heuristic_fallback_missing_openai_key", (
                    {"skill_id": heuristic_id, "reasoning": "heuristic keyword match"} if heuristic_id else None
                )
            result = _generate_openai_skill_decision(question)
            if result is not None:
                set_cached_planner_result("skill_planner", cache_payload, result)
            return "llm_openai", result

        if provider == "gemini":
            if not settings.gemini_api_key:
                heuristic_id = _heuristic_skill_dispatch(question)
                return "heuristic_fallback_missing_gemini_key", (
                    {"skill_id": heuristic_id, "reasoning": "heuristic keyword match"} if heuristic_id else None
                )
            result = _generate_gemini_skill_decision(question)
            if result is not None:
                set_cached_planner_result("skill_planner", cache_payload, result)
            return "llm_gemini", result

    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        heuristic_id = _heuristic_skill_dispatch(question)
        return f"heuristic_fallback_after_{provider}_error", (
            {"skill_id": heuristic_id, "reasoning": "heuristic keyword match"} if heuristic_id else None
        )

    heuristic_id = _heuristic_skill_dispatch(question)
    return "heuristic_fallback_unsupported_provider", (
        {"skill_id": heuristic_id, "reasoning": "heuristic keyword match"} if heuristic_id else None
    )
