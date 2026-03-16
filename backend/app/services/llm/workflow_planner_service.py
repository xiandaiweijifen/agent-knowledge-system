import json
from pathlib import Path
from typing import Any

import httpx

from app.core.config import DATA_ROOT
from app.core.config import settings
from app.services.llm.planner_cache_service import (
    get_cached_planner_result,
    set_cached_planner_result,
)
from app.services.agent.state_store import atomic_write_json


OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_GENERATE_CONTENT_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/{model_name}:generateContent"
)
WORKFLOW_PLANNER_DEBUG_PATH = DATA_ROOT / "tool_state" / ".tmp" / "workflow_planner_debug.json"


def _resolve_openai_workflow_planner_model() -> str:
    return settings.openai_workflow_planner_model.strip() or settings.openai_chat_model


def _resolve_gemini_workflow_planner_model() -> str:
    return settings.gemini_workflow_planner_model.strip() or settings.gemini_chat_model


def _strip_json_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```JSON").removeprefix("```")
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    return cleaned.strip()


def _capture_workflow_planner_debug(payload: dict[str, Any]) -> None:
    if not settings.workflow_planner_debug_capture:
        return
    atomic_write_json(WORKFLOW_PLANNER_DEBUG_PATH, payload)


def _extract_first_json_object(text: str) -> str:
    cleaned = _strip_json_fences(text)
    if not cleaned:
        return ""

    start = cleaned.find("{")
    if start == -1:
        return cleaned

    depth = 0
    for index in range(start, len(cleaned)):
        char = cleaned[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return cleaned[start : index + 1]
    return cleaned


def _extract_text_from_candidate_payload(payload: Any) -> list[str]:
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


def _build_workflow_planner_prompt(question: str) -> str:
    return (
        "You are a workflow planning assistant for an enterprise agent system. "
        "Decide whether the user request should stay single-step or be decomposed into a supported multi-step workflow. "
        "Return JSON only with keys: workflow_kind, search_question, follow_up_question. "
        "workflow_kind must be one of: single_step, search_then_ticket, search_then_summarize, status_then_ticket, status_then_summarize. "
        "If workflow_kind is single_step, return empty strings for search_question and follow_up_question. "
        "If workflow_kind is search_then_ticket, search_question must contain the search step and "
        "follow_up_question must contain the ticket step, which may create, update, or close a ticket. "
        "If workflow_kind is search_then_summarize, search_question must contain the search step and "
        "follow_up_question must contain the summary step. "
        "If workflow_kind is status_then_ticket, search_question must contain the system status step and "
        "follow_up_question must contain the ticket step, which may create, update, or close a ticket. "
        "If workflow_kind is status_then_summarize, search_question must contain the system status step and "
        "follow_up_question must contain the summary step. "
        "Use single_step if the request is not clearly a supported multi-step workflow. "
        "Good examples:\n"
        '- "Search docs for payment-service outage and create a high severity ticket for payment-service" '
        '-> {"workflow_kind":"search_then_ticket","search_question":"Search docs for payment-service outage",'
        '"follow_up_question":"create a high severity ticket for payment-service"}\n'
        '- "Search docs for payment-service outage and update ticket TICKET-0010 for payment-service status to closed" '
        '-> {"workflow_kind":"search_then_ticket","search_question":"Search docs for payment-service outage",'
        '"follow_up_question":"update ticket TICKET-0010 for payment-service status to closed"}\n'
        '- "Look up docs about RAG, then summarize top 1 results" '
        '-> {"workflow_kind":"search_then_summarize","search_question":"Look up docs about RAG",'
        '"follow_up_question":"summarize top 1 results"}\n'
        '- "Check system status for payment-service, then create a high severity ticket for payment-service" '
        '-> {"workflow_kind":"status_then_ticket","search_question":"Check system status for payment-service",'
        '"follow_up_question":"create a high severity ticket for payment-service"}\n'
        '- "Check system status for payment-service, then update ticket TICKET-0010 for payment-service status to closed" '
        '-> {"workflow_kind":"status_then_ticket","search_question":"Check system status for payment-service",'
        '"follow_up_question":"update ticket TICKET-0010 for payment-service status to closed"}\n'
        '- "Check system status for payment-service, then summarize the result" '
        '-> {"workflow_kind":"status_then_summarize","search_question":"Check system status for payment-service",'
        '"follow_up_question":"summarize the result"}\n'
        '- "Create a ticket for payment-service outage" '
        '-> {"workflow_kind":"single_step","search_question":"","follow_up_question":""}\n'
        "Preserve clear user constraints like filename, max_results, severity, environment, and target. "
        "Do not include markdown fences or explanations.\n\n"
        f"User request: {question}"
    )


def _normalize_workflow_kind(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "single": "single_step",
        "single_step": "single_step",
        "singletool": "single_step",
        "single_tool": "single_step",
        "search_ticket": "search_then_ticket",
        "search_then_ticket": "search_then_ticket",
        "search_to_ticket": "search_then_ticket",
        "search_summary": "search_then_summarize",
        "search_then_summary": "search_then_summarize",
        "search_then_summarize": "search_then_summarize",
        "search_to_summary": "search_then_summarize",
        "status_ticket": "status_then_ticket",
        "status_then_ticket": "status_then_ticket",
        "status_check_then_ticket": "status_then_ticket",
        "check_status_then_ticket": "status_then_ticket",
        "status_to_ticket": "status_then_ticket",
        "status_summary": "status_then_summarize",
        "status_then_summary": "status_then_summarize",
        "status_then_summarize": "status_then_summarize",
        "status_check_then_summary": "status_then_summarize",
        "check_status_then_summary": "status_then_summarize",
        "status_to_summary": "status_then_summarize",
    }
    return aliases.get(normalized, normalized)


def _normalize_workflow_plan_payload(payload: dict) -> dict[str, str] | None:
    workflow_kind = payload.get("workflow_kind") or payload.get("workflow_type")
    search_question = payload.get("search_question", "")
    follow_up_question = payload.get("follow_up_question", "")

    if not search_question and isinstance(payload.get("search_step"), str):
        search_question = payload["search_step"]
    if not follow_up_question and isinstance(payload.get("action_step"), str):
        follow_up_question = payload["action_step"]
    if not follow_up_question and isinstance(payload.get("summary_step"), str):
        follow_up_question = payload["summary_step"]

    if not isinstance(workflow_kind, str):
        return None
    normalized_kind = _normalize_workflow_kind(workflow_kind)
    if normalized_kind not in {
        "single_step",
        "search_then_ticket",
        "search_then_summarize",
        "status_then_ticket",
        "status_then_summarize",
    }:
        return None

    if not isinstance(search_question, str) or not isinstance(follow_up_question, str):
        return None

    normalized_payload = {
        "workflow_kind": normalized_kind,
        "search_question": search_question.strip(),
        "follow_up_question": follow_up_question.strip(),
    }

    if normalized_kind == "single_step":
        return normalized_payload

    if not normalized_payload["search_question"] or not normalized_payload["follow_up_question"]:
        return None

    return normalized_payload


def _parse_llm_workflow_plan_response(raw_text: str) -> dict[str, str] | None:
    cleaned = _extract_first_json_object(raw_text)
    if not cleaned:
        return None

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    return _normalize_workflow_plan_payload(payload)


def _extract_gemini_workflow_plan_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return ""

    texts: list[str] = []
    for candidate in candidates:
        texts.extend(_extract_text_from_candidate_payload(candidate))

    cleaned_texts = [text.strip() for text in texts if isinstance(text, str) and text.strip()]
    return "\n".join(cleaned_texts).strip()


def _generate_openai_workflow_plan(question: str) -> dict[str, str] | None:
    model_name = _resolve_openai_workflow_planner_model()
    response = httpx.post(
        OPENAI_CHAT_COMPLETIONS_URL,
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model_name,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "Return valid JSON only."},
                {"role": "user", "content": _build_workflow_planner_prompt(question)},
            ],
        },
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    _capture_workflow_planner_debug(
        {
            "provider": "openai",
            "model": model_name,
            "question": question,
            "status": "success" if isinstance(content, str) else "missing_content",
            "response_json": payload,
            "raw_text": content if isinstance(content, str) else None,
        }
    )
    if not isinstance(content, str):
        return None
    return _parse_llm_workflow_plan_response(content)


def _generate_gemini_workflow_plan(question: str) -> dict[str, str] | None:
    model_name = _resolve_gemini_workflow_planner_model()
    response = httpx.post(
        GEMINI_GENERATE_CONTENT_URL_TEMPLATE.format(model_name=model_name),
        headers={
            "x-goog-api-key": settings.gemini_api_key,
            "Content-Type": "application/json",
        },
        json={
            "contents": [{"role": "user", "parts": [{"text": _build_workflow_planner_prompt(question)}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        },
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    content = _extract_gemini_workflow_plan_text(payload)
    parsed_plan = _parse_llm_workflow_plan_response(content) if content else None
    _capture_workflow_planner_debug(
        {
            "provider": "gemini",
            "model": model_name,
            "question": question,
            "status": (
                "parsed_success"
                if parsed_plan is not None
                else "parse_failed"
                if content
                else "missing_text"
            ),
            "response_json": payload,
            "raw_text": content or None,
            "parsed_plan": parsed_plan,
        }
    )
    return parsed_plan


def generate_llm_workflow_plan(question: str) -> tuple[str, dict[str, str] | None]:
    provider = settings.workflow_planner_provider.lower().strip()

    if provider == "fallback":
        return "heuristic_stub", None

    cache_payload = {
        "provider": provider,
        "question": question,
    }
    cached_plan = get_cached_planner_result("workflow_planner", cache_payload)
    if cached_plan is not None:
        _capture_workflow_planner_debug(
            {
                "provider": provider,
                "question": question,
                "status": "cache_hit",
                "parsed_plan": cached_plan,
            }
        )
        return f"llm_{provider}", cached_plan

    try:
        if provider == "openai":
            if not settings.openai_api_key:
                return "heuristic_fallback_missing_openai_key", None
            plan = _generate_openai_workflow_plan(question)
            if plan is not None:
                set_cached_planner_result("workflow_planner", cache_payload, plan)
            return "llm_openai", plan

        if provider == "gemini":
            if not settings.gemini_api_key:
                return "heuristic_fallback_missing_gemini_key", None
            plan = _generate_gemini_workflow_plan(question)
            if plan is not None:
                set_cached_planner_result("workflow_planner", cache_payload, plan)
            return "llm_gemini", plan
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        _capture_workflow_planner_debug(
            {
                "provider": provider,
                "question": question,
                "status": "exception",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }
        )
        return f"heuristic_fallback_after_{provider}_error", None

    return "heuristic_fallback_unsupported_provider", None
