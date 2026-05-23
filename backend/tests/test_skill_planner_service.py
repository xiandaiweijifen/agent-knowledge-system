"""Unit tests for the LLM-backed skill planner service."""

import json

import httpx
import pytest

from app.services.llm.skill_planner_service import (
    _heuristic_skill_dispatch,
    _normalize_skill_payload,
    _parse_llm_skill_response,
    generate_llm_skill_decision,
)


# ---------------------------------------------------------------------------
# _heuristic_skill_dispatch
# ---------------------------------------------------------------------------


def test_heuristic_returns_incident_triage_for_triage_keyword():
    result = _heuristic_skill_dispatch("Please triage the payment-service")
    assert result == "incident_triage"


def test_heuristic_returns_incident_triage_for_incident_and_action():
    result = _heuristic_skill_dispatch("Check payment-service for the outage and draft a ticket")
    assert result == "incident_triage"


def test_heuristic_returns_service_runtime_review_for_status_and_action():
    result = _heuristic_skill_dispatch("Check payment-service in production status")
    assert result == "service_runtime_review"


def test_heuristic_returns_none_for_simple_create():
    result = _heuristic_skill_dispatch("Create a ticket for payment-service outage")
    assert result is None


def test_heuristic_returns_none_for_unrelated_question():
    result = _heuristic_skill_dispatch("What documents do we have?")
    assert result is None


# ---------------------------------------------------------------------------
# _normalize_skill_payload
# ---------------------------------------------------------------------------


def test_normalize_accepts_valid_skill_id():
    result = _normalize_skill_payload({"skill_id": "incident_triage", "reasoning": "reason"})
    assert result == {"skill_id": "incident_triage", "reasoning": "reason"}


def test_normalize_accepts_single_tool():
    result = _normalize_skill_payload({"skill_id": "single_tool", "reasoning": ""})
    assert result == {"skill_id": "single_tool", "reasoning": ""}


def test_normalize_rejects_unknown_skill_id():
    result = _normalize_skill_payload({"skill_id": "unknown_workflow", "reasoning": "x"})
    assert result is None


def test_normalize_rejects_non_string_skill_id():
    result = _normalize_skill_payload({"skill_id": 42, "reasoning": "x"})
    assert result is None


def test_normalize_strips_and_lowercases_skill_id():
    result = _normalize_skill_payload({"skill_id": "  Incident_Triage  ", "reasoning": "x"})
    assert result == {"skill_id": "incident_triage", "reasoning": "x"}


# ---------------------------------------------------------------------------
# _parse_llm_skill_response
# ---------------------------------------------------------------------------


def test_parse_valid_json_response():
    raw = json.dumps({"skill_id": "service_runtime_review", "reasoning": "health check"})
    result = _parse_llm_skill_response(raw)
    assert result == {"skill_id": "service_runtime_review", "reasoning": "health check"}


def test_parse_strips_json_fences():
    raw = "```json\n" + json.dumps({"skill_id": "single_tool", "reasoning": ""}) + "\n```"
    result = _parse_llm_skill_response(raw)
    assert result is not None
    assert result["skill_id"] == "single_tool"


def test_parse_returns_none_for_invalid_json():
    result = _parse_llm_skill_response("not json at all")
    assert result is None


def test_parse_returns_none_for_empty_string():
    result = _parse_llm_skill_response("")
    assert result is None


def test_parse_returns_none_for_invalid_skill_id():
    raw = json.dumps({"skill_id": "made_up_skill", "reasoning": "x"})
    result = _parse_llm_skill_response(raw)
    assert result is None


# ---------------------------------------------------------------------------
# generate_llm_skill_decision — fallback provider
# ---------------------------------------------------------------------------


def test_generate_returns_heuristic_for_fallback_provider(monkeypatch):
    monkeypatch.setattr("app.services.llm.skill_planner_service.settings.skill_planner_provider", "fallback")
    mode, payload = generate_llm_skill_decision("triage the auth-service incident")
    assert mode == "heuristic_fallback"
    assert payload is not None
    assert payload["skill_id"] == "incident_triage"


def test_generate_returns_none_payload_when_heuristic_misses(monkeypatch):
    monkeypatch.setattr("app.services.llm.skill_planner_service.settings.skill_planner_provider", "fallback")
    mode, payload = generate_llm_skill_decision("What documents do we have?")
    assert mode == "heuristic_fallback"
    assert payload is None


# ---------------------------------------------------------------------------
# generate_llm_skill_decision — OpenAI provider
# ---------------------------------------------------------------------------


def test_generate_openai_returns_parsed_skill(monkeypatch):
    monkeypatch.setattr("app.services.llm.skill_planner_service.settings.skill_planner_provider", "openai")
    monkeypatch.setattr("app.services.llm.skill_planner_service.settings.openai_api_key", "test-key")
    monkeypatch.setattr(
        "app.services.llm.skill_planner_service.get_cached_planner_result",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        "app.services.llm.skill_planner_service.set_cached_planner_result",
        lambda *a, **kw: None,
    )

    tool_call_payload = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "function": {
                                "arguments": json.dumps({"skill_id": "incident_triage", "reasoning": "mock"})
                            }
                        }
                    ]
                }
            }
        ]
    }

    class _MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return tool_call_payload

    monkeypatch.setattr("httpx.post", lambda *a, **kw: _MockResponse())

    mode, payload = generate_llm_skill_decision("check auth-service for outage and triage")
    assert mode == "llm_openai"
    assert payload is not None
    assert payload["skill_id"] == "incident_triage"


def test_generate_openai_falls_back_on_http_error(monkeypatch):
    monkeypatch.setattr("app.services.llm.skill_planner_service.settings.skill_planner_provider", "openai")
    monkeypatch.setattr("app.services.llm.skill_planner_service.settings.openai_api_key", "test-key")
    monkeypatch.setattr(
        "app.services.llm.skill_planner_service.get_cached_planner_result",
        lambda *a, **kw: None,
    )

    def _raise(*a, **kw):
        raise httpx.HTTPError("connection refused")

    monkeypatch.setattr("httpx.post", _raise)

    mode, payload = generate_llm_skill_decision("triage auth-service incident")
    assert "heuristic_fallback_after_openai_error" in mode
    assert payload is not None
    assert payload["skill_id"] == "incident_triage"


def test_generate_openai_falls_back_when_key_missing(monkeypatch):
    monkeypatch.setattr("app.services.llm.skill_planner_service.settings.skill_planner_provider", "openai")
    monkeypatch.setattr("app.services.llm.skill_planner_service.settings.openai_api_key", "")

    mode, payload = generate_llm_skill_decision("check auth-service status")
    assert "heuristic_fallback_missing_openai_key" in mode


# ---------------------------------------------------------------------------
# generate_llm_skill_decision — Gemini provider
# ---------------------------------------------------------------------------


def test_generate_gemini_returns_parsed_skill(monkeypatch):
    monkeypatch.setattr("app.services.llm.skill_planner_service.settings.skill_planner_provider", "gemini")
    monkeypatch.setattr("app.services.llm.skill_planner_service.settings.gemini_api_key", "test-key")
    monkeypatch.setattr(
        "app.services.llm.skill_planner_service.get_cached_planner_result",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        "app.services.llm.skill_planner_service.set_cached_planner_result",
        lambda *a, **kw: None,
    )

    gemini_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": json.dumps({"skill_id": "service_runtime_review", "reasoning": "health check"})}]
                }
            }
        ]
    }

    class _MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return gemini_payload

    monkeypatch.setattr("httpx.post", lambda *a, **kw: _MockResponse())

    mode, payload = generate_llm_skill_decision("check payment-service health")
    assert mode == "llm_gemini"
    assert payload is not None
    assert payload["skill_id"] == "service_runtime_review"


def test_generate_gemini_falls_back_on_http_error(monkeypatch):
    monkeypatch.setattr("app.services.llm.skill_planner_service.settings.skill_planner_provider", "gemini")
    monkeypatch.setattr("app.services.llm.skill_planner_service.settings.gemini_api_key", "test-key")
    monkeypatch.setattr(
        "app.services.llm.skill_planner_service.get_cached_planner_result",
        lambda *a, **kw: None,
    )

    def _raise(*a, **kw):
        raise httpx.HTTPError("connection refused")

    monkeypatch.setattr("httpx.post", _raise)

    mode, payload = generate_llm_skill_decision("check payment-service status")
    assert "heuristic_fallback_after_gemini_error" in mode


def test_generate_gemini_falls_back_when_key_missing(monkeypatch):
    monkeypatch.setattr("app.services.llm.skill_planner_service.settings.skill_planner_provider", "gemini")
    monkeypatch.setattr("app.services.llm.skill_planner_service.settings.gemini_api_key", "")

    mode, payload = generate_llm_skill_decision("check payment-service health")
    assert "heuristic_fallback_missing_gemini_key" in mode


# ---------------------------------------------------------------------------
# generate_llm_skill_decision — cache hit
# ---------------------------------------------------------------------------


def test_generate_returns_cached_result(monkeypatch):
    monkeypatch.setattr("app.services.llm.skill_planner_service.settings.skill_planner_provider", "gemini")
    monkeypatch.setattr("app.services.llm.skill_planner_service.settings.gemini_api_key", "test-key")

    cached = {"skill_id": "incident_triage", "reasoning": "cached"}
    monkeypatch.setattr(
        "app.services.llm.skill_planner_service.get_cached_planner_result",
        lambda *a, **kw: cached,
    )

    mode, payload = generate_llm_skill_decision("any question")
    assert mode == "llm_gemini"
    assert payload == cached


# ---------------------------------------------------------------------------
# generate_llm_skill_decision — unsupported provider
# ---------------------------------------------------------------------------


def test_generate_falls_back_for_unsupported_provider(monkeypatch):
    monkeypatch.setattr("app.services.llm.skill_planner_service.settings.skill_planner_provider", "anthropic")

    mode, payload = generate_llm_skill_decision("triage the incident")
    assert "heuristic_fallback_unsupported_provider" in mode
