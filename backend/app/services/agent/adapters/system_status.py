"""System status tool adapter — inspect service health snapshots."""

import uuid
from typing import Any

from app.core.config import settings
from app.schemas.tools import ToolExecutionRequest, ToolExecutionResponse
from app.services.ingestion.document_service import build_utc_timestamp

from app.services.agent.adapters._shared import (
    _build_service_record,
    _build_status_snapshot,
    _build_tool_output_metadata,
    _normalize_environment_value,
    _normalize_status_scenario_value,
)
from app.services.agent.adapters.registry import register_adapter


def _build_system_status_output(
    target: str,
    requested_environment: str = "",
    requested_scenario: str = "",
) -> dict[str, Any]:
    embedding_model = (
        settings.gemini_embedding_model
        if settings.embedding_provider == "gemini"
        else settings.openai_embedding_model
        if settings.embedding_provider == "openai"
        else "mock-embedding-v1"
    )
    chat_model = (
        settings.gemini_chat_model
        if settings.chat_provider == "gemini"
        else settings.openai_chat_model
        if settings.chat_provider == "openai"
        else "local-fallback"
    )

    service_record = _build_service_record(target)
    environment = requested_environment or settings.app_env or "development"
    status_snapshot = _build_status_snapshot(service_record, environment, requested_scenario)

    output = {
        **_build_tool_output_metadata(
            output_kind="status_snapshot",
            resource_type="system_status",
            target=target,
        ),
        "status": "ok" if status_snapshot.health == "healthy" else status_snapshot.health,
        "app_env": settings.app_env,
        "service": service_record.service_id,
        "environment": status_snapshot.environment,
        "health": status_snapshot.health,
        "scenario_id": status_snapshot.scenario_id,
        "latency_p95_ms": status_snapshot.latency_p95_ms,
        "error_rate": status_snapshot.error_rate,
        "cpu_percent": status_snapshot.cpu_percent,
        "memory_percent": status_snapshot.memory_percent,
        "active_alerts": status_snapshot.active_alerts,
        "summary": status_snapshot.summary,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": embedding_model,
        "chat_provider": settings.chat_provider,
        "chat_model": chat_model,
        "gemini_configured": str(bool(settings.gemini_api_key)).lower(),
        "openai_configured": str(bool(settings.openai_api_key)).lower(),
        "database_configured": str(bool(settings.database_url)).lower(),
        "redis_configured": str(bool(settings.redis_url)).lower(),
        "service_record": service_record.model_dump(mode="json"),
        "status_snapshot": status_snapshot.model_dump(mode="json"),
    }
    if requested_environment:
        output["requested_environment"] = requested_environment
    if requested_scenario:
        output["requested_scenario"] = _normalize_status_scenario_value(requested_scenario)
    return output


def _run_system_status_tool(request: ToolExecutionRequest) -> ToolExecutionResponse:
    target = request.target.strip()
    action = request.action.strip().lower()
    requested_environment = _normalize_environment_value(
        request.arguments.get("environment", "").strip()
    )
    requested_scenario = _normalize_status_scenario_value(
        request.arguments.get("scenario", "").strip()
    )
    output = _build_system_status_output(
        target,
        requested_environment=requested_environment,
        requested_scenario=requested_scenario,
    )
    return ToolExecutionResponse(
        tool_name="system_status",
        action=action,
        target=target,
        execution_status="completed",
        execution_mode="local_adapter",
        result_summary=(
            f"Collected local system status for {target or 'agent-knowledge-system'}"
            + (
                f" with requested environment {requested_environment}."
                if requested_environment
                else "."
            )
            + (
                f" Scenario {requested_scenario} selected."
                if requested_scenario
                else ""
            )
        ),
        trace_id=uuid.uuid4().hex,
        executed_at=build_utc_timestamp(),
        output=output,
    )


register_adapter("system_status", _run_system_status_tool)
