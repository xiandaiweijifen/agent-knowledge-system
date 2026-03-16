import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import DATA_ROOT

REPORT_STORE_DIR = DATA_ROOT / "tool_state" / "evaluation_reports"


def _sanitize_segment(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()) or "default"


def _ensure_report_store_dir() -> None:
    REPORT_STORE_DIR.mkdir(parents=True, exist_ok=True)


def _report_payload(dataset_name: str, report: Any, report_source: str) -> dict[str, Any]:
    if hasattr(report, "model_dump"):
        serialized_report = report.model_dump(mode="json")
    else:
        serialized_report = report

    return {
        "dataset_name": dataset_name,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "report_source": report_source,
        "report": serialized_report,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_report_store_dir()
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return payload


def _read_report(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _history_timestamp(saved_at: str) -> str:
    return (
        saved_at.replace("-", "")
        .replace(":", "")
        .replace("+00:00", "Z")
        .replace(".", "_")
    )


def _retrieval_report_path(dataset_name: str, top_k: int) -> Path:
    safe_name = _sanitize_segment(dataset_name)
    return REPORT_STORE_DIR / f"retrieval__{safe_name}__topk_{top_k}.json"


def _retrieval_history_report_path(dataset_name: str, top_k: int, saved_at: str) -> Path:
    safe_name = _sanitize_segment(dataset_name)
    return REPORT_STORE_DIR / (
        f"retrieval__{safe_name}__topk_{top_k}__{_history_timestamp(saved_at)}.json"
    )


def _agent_route_report_path(dataset_name: str) -> Path:
    safe_name = _sanitize_segment(dataset_name)
    return REPORT_STORE_DIR / f"agent_route__{safe_name}.json"


def _agent_route_history_report_path(dataset_name: str, saved_at: str) -> Path:
    safe_name = _sanitize_segment(dataset_name)
    return REPORT_STORE_DIR / f"agent_route__{safe_name}__{_history_timestamp(saved_at)}.json"


def _agent_workflow_report_path(dataset_name: str) -> Path:
    safe_name = _sanitize_segment(dataset_name)
    return REPORT_STORE_DIR / f"agent_workflow__{safe_name}.json"


def _agent_workflow_history_report_path(dataset_name: str, saved_at: str) -> Path:
    safe_name = _sanitize_segment(dataset_name)
    return REPORT_STORE_DIR / f"agent_workflow__{safe_name}__{_history_timestamp(saved_at)}.json"


def _tool_execution_report_path(dataset_name: str) -> Path:
    safe_name = _sanitize_segment(dataset_name)
    return REPORT_STORE_DIR / f"tool_execution__{safe_name}.json"


def _tool_execution_history_report_path(dataset_name: str, saved_at: str) -> Path:
    safe_name = _sanitize_segment(dataset_name)
    return REPORT_STORE_DIR / f"tool_execution__{safe_name}__{_history_timestamp(saved_at)}.json"


def _history_entry(payload: dict[str, Any], primary_metric_name: str, primary_metric_value: float) -> dict[str, Any]:
    return {
        "dataset_name": payload["dataset_name"],
        "saved_at": payload["saved_at"],
        "report_source": "saved",
        "top_k": payload.get("top_k"),
        "primary_metric_name": primary_metric_name,
        "primary_metric_value": primary_metric_value,
        "case_count": payload["report"]["summary"]["total_cases"],
    }


def _sorted_history_payloads(paths: list[Path]) -> list[dict[str, Any]]:
    payloads = []
    for path in paths:
        payload = _read_report(path)
        if payload is not None:
            payloads.append(payload)
    payloads.sort(key=lambda item: item["saved_at"], reverse=True)
    return payloads


def persist_retrieval_report(dataset_name: str, top_k: int, report: Any) -> dict[str, Any]:
    payload = _report_payload(dataset_name=dataset_name, report=report, report_source="fresh")
    payload["top_k"] = top_k
    _write_report(_retrieval_history_report_path(dataset_name, top_k, payload["saved_at"]), payload)
    return _write_report(_retrieval_report_path(dataset_name, top_k), payload)


def load_latest_retrieval_report(dataset_name: str, top_k: int) -> dict[str, Any] | None:
    payload = _read_report(_retrieval_report_path(dataset_name, top_k))
    if payload is None:
        return None
    payload["report_source"] = "saved"
    return payload


def list_retrieval_report_history(dataset_name: str, top_k: int, limit: int = 5) -> list[dict[str, Any]]:
    safe_name = _sanitize_segment(dataset_name)
    pattern = f"retrieval__{safe_name}__topk_{top_k}__*.json"
    payloads = _sorted_history_payloads(sorted(REPORT_STORE_DIR.glob(pattern)))[:limit]
    return [
        _history_entry(
            payload=payload,
            primary_metric_name="hit_rate_at_k",
            primary_metric_value=payload["report"]["summary"]["hit_rate_at_k"],
        )
        for payload in payloads
    ]


def persist_agent_route_report(dataset_name: str, report: Any) -> dict[str, Any]:
    payload = _report_payload(dataset_name=dataset_name, report=report, report_source="fresh")
    _write_report(_agent_route_history_report_path(dataset_name, payload["saved_at"]), payload)
    return _write_report(_agent_route_report_path(dataset_name), payload)


def load_latest_agent_route_report(dataset_name: str) -> dict[str, Any] | None:
    payload = _read_report(_agent_route_report_path(dataset_name))
    if payload is None:
        return None
    payload["report_source"] = "saved"
    return payload


def list_agent_route_report_history(dataset_name: str, limit: int = 5) -> list[dict[str, Any]]:
    safe_name = _sanitize_segment(dataset_name)
    pattern = f"agent_route__{safe_name}__*.json"
    payloads = _sorted_history_payloads(sorted(REPORT_STORE_DIR.glob(pattern)))[:limit]
    return [
        _history_entry(
            payload=payload,
            primary_metric_name="route_accuracy",
            primary_metric_value=payload["report"]["summary"]["route_accuracy"],
        )
        for payload in payloads
    ]


def persist_agent_workflow_report(dataset_name: str, report: Any) -> dict[str, Any]:
    payload = _report_payload(dataset_name=dataset_name, report=report, report_source="fresh")
    _write_report(_agent_workflow_history_report_path(dataset_name, payload["saved_at"]), payload)
    return _write_report(_agent_workflow_report_path(dataset_name), payload)


def load_latest_agent_workflow_report(dataset_name: str) -> dict[str, Any] | None:
    payload = _read_report(_agent_workflow_report_path(dataset_name))
    if payload is None:
        return None
    payload["report_source"] = "saved"
    return payload


def list_agent_workflow_report_history(dataset_name: str, limit: int = 5) -> list[dict[str, Any]]:
    safe_name = _sanitize_segment(dataset_name)
    pattern = f"agent_workflow__{safe_name}__*.json"
    payloads = _sorted_history_payloads(sorted(REPORT_STORE_DIR.glob(pattern)))[:limit]
    return [
        _history_entry(
            payload=payload,
            primary_metric_name="workflow_accuracy",
            primary_metric_value=payload["report"]["summary"]["workflow_accuracy"],
        )
        for payload in payloads
    ]


def persist_tool_execution_report(dataset_name: str, report: Any) -> dict[str, Any]:
    payload = _report_payload(dataset_name=dataset_name, report=report, report_source="fresh")
    _write_report(_tool_execution_history_report_path(dataset_name, payload["saved_at"]), payload)
    return _write_report(_tool_execution_report_path(dataset_name), payload)


def load_latest_tool_execution_report(dataset_name: str) -> dict[str, Any] | None:
    payload = _read_report(_tool_execution_report_path(dataset_name))
    if payload is None:
        return None
    payload["report_source"] = "saved"
    return payload


def list_tool_execution_report_history(dataset_name: str, limit: int = 5) -> list[dict[str, Any]]:
    safe_name = _sanitize_segment(dataset_name)
    pattern = f"tool_execution__{safe_name}__*.json"
    payloads = _sorted_history_payloads(sorted(REPORT_STORE_DIR.glob(pattern)))[:limit]
    return [
        _history_entry(
            payload=payload,
            primary_metric_name="tool_accuracy",
            primary_metric_value=payload["report"]["summary"]["tool_accuracy"],
        )
        for payload in payloads
    ]
