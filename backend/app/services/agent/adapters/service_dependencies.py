"""Service dependencies tool adapter — inspect downstream dependency maps."""

import uuid
from typing import Any

from app.schemas.domain import ServiceDependency
from app.schemas.tools import ToolExecutionRequest, ToolExecutionResponse
from app.services.ingestion.document_service import build_utc_timestamp

from app.services.agent.adapters._shared import (
    ENGINEERING_DEPENDENCY_MAP_PATH,
    _build_service_record,
    _build_tool_output_metadata,
    _canonicalize_service_id,
    _load_engineering_dependency_map,
    _normalize_dependency_name,
    _normalize_environment_value,
    _normalize_failure_signal,
)
from app.services.agent.adapters.registry import register_adapter


def _build_service_dependencies_output(
    target: str,
    requested_environment: str = "",
    requested_failure_signal: str = "",
    requested_dependency_name: str = "",
) -> dict[str, Any]:
    service_record = _build_service_record(target)
    normalized_environment = _normalize_environment_value(
        requested_environment or "development"
    )
    normalized_failure_signal = _normalize_failure_signal(requested_failure_signal)
    normalized_dependency_name = _normalize_dependency_name(requested_dependency_name)

    selected_entry: dict[str, Any] | None = None
    for item in _load_engineering_dependency_map():
        if not isinstance(item, dict):
            continue
        service_id = _canonicalize_service_id(str(item.get("service") or ""))
        environment = _normalize_environment_value(str(item.get("environment") or ""))
        if service_id == service_record.service_id and environment == normalized_environment:
            selected_entry = item
            break

    raw_dependencies = []
    if isinstance(selected_entry, dict):
        raw_dependencies = selected_entry.get("downstream_dependencies", [])
        raw_dependencies = raw_dependencies if isinstance(raw_dependencies, list) else []

    indexed_dependency_records: list[tuple[int, ServiceDependency]] = []
    for index, item in enumerate(raw_dependencies):
        if not isinstance(item, dict):
            continue
        record = ServiceDependency(
            name=str(item.get("name") or "").strip(),
            type=str(item.get("type") or "unknown").strip() or "unknown",
            criticality=str(item.get("criticality") or "unspecified").strip() or "unspecified",
            failure_signals=[
                str(signal).strip()
                for signal in item.get("failure_signals", [])
                if str(signal).strip()
            ],
            recommended_checks=[
                str(check).strip()
                for check in item.get("recommended_checks", [])
                if str(check).strip()
            ],
        )
        if record.name:
            indexed_dependency_records.append((index, record))

    def _dependency_priority(item: tuple[int, ServiceDependency]) -> tuple[int, int, int]:
        index, record = item
        matches_name = (
            1
            if normalized_dependency_name
            and _normalize_dependency_name(record.name) == normalized_dependency_name
            else 0
        )
        matches_signal = (
            1
            if normalized_failure_signal
            and any(
                _normalize_failure_signal(signal) == normalized_failure_signal
                for signal in record.failure_signals
            )
            else 0
        )
        return (-matches_name, -matches_signal, index)

    indexed_dependency_records.sort(key=_dependency_priority)
    dependency_records = [record for _, record in indexed_dependency_records]

    primary_dependency = dependency_records[0].name if dependency_records else ""
    aggregated_checks: list[str] = []
    for record in dependency_records[:2]:
        for check in record.recommended_checks:
            if check not in aggregated_checks:
                aggregated_checks.append(check)

    signal_matched = any(
        _normalize_failure_signal(signal) == normalized_failure_signal
        for record in dependency_records
        for signal in record.failure_signals
    )
    summary = (
        f"Dependency review for {service_record.service_name} in {normalized_environment} "
        f"found {len(dependency_records)} downstream dependenc"
        f"{'y' if len(dependency_records) == 1 else 'ies'}."
    )
    if primary_dependency:
        summary += f" Primary dependency to inspect: {primary_dependency}."
    if normalized_failure_signal:
        if signal_matched:
            summary += f" Requested failure signal {normalized_failure_signal} matched the returned dependencies."
        else:
            summary += f" Requested failure signal {normalized_failure_signal} was not found in the selected dependency map."

    output: dict[str, Any] = {
        **_build_tool_output_metadata(
            output_kind="dependency_snapshot",
            resource_type="service_dependency",
            target=target,
            item_count=len(dependency_records),
        ),
        "service": service_record.service_id,
        "environment": normalized_environment,
        "service_record": service_record.model_dump(mode="json"),
        "dependencies": [record.model_dump(mode="json") for record in dependency_records],
        "dependency_count": str(len(dependency_records)),
        "source_filename": ENGINEERING_DEPENDENCY_MAP_PATH.name,
        "summary": summary,
        "recommended_checks": aggregated_checks,
    }
    if primary_dependency:
        output["suspected_primary_dependency"] = primary_dependency
    if requested_environment:
        output["requested_environment"] = normalized_environment
    if normalized_failure_signal:
        output["requested_failure_signal"] = normalized_failure_signal
        output["matched_failure_signal"] = str(signal_matched).lower()
    if normalized_dependency_name:
        output["requested_dependency_name"] = normalized_dependency_name
    return output


def _run_service_dependencies_tool(request: ToolExecutionRequest) -> ToolExecutionResponse:
    target = request.target.strip()
    requested_environment = _normalize_environment_value(
        request.arguments.get("environment", "").strip()
    )
    requested_failure_signal = _normalize_failure_signal(
        request.arguments.get("failure_signal", "").strip()
    )
    requested_dependency_name = _normalize_dependency_name(
        request.arguments.get("dependency_name", "").strip()
    )
    output = _build_service_dependencies_output(
        target,
        requested_environment=requested_environment,
        requested_failure_signal=requested_failure_signal,
        requested_dependency_name=requested_dependency_name,
    )
    dependency_count = int(output.get("dependency_count") or 0)
    result_summary = (
        f"Loaded {dependency_count} downstream dependenc"
        f"{'y' if dependency_count == 1 else 'ies'} for {target}."
    )
    if requested_environment:
        result_summary += f" Environment {requested_environment} selected."
    if output.get("suspected_primary_dependency"):
        result_summary += f" Primary dependency: {output['suspected_primary_dependency']}."

    return ToolExecutionResponse(
        tool_name="service_dependencies",
        action=request.action,
        target=target,
        execution_status="completed",
        execution_mode="local_adapter",
        result_summary=result_summary,
        trace_id=uuid.uuid4().hex,
        executed_at=build_utc_timestamp(),
        output=output,
    )


register_adapter("service_dependencies", _run_service_dependencies_tool)
