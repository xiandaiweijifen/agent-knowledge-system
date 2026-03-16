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


def _retrieval_report_path(dataset_name: str, top_k: int) -> Path:
    safe_name = _sanitize_segment(dataset_name)
    return REPORT_STORE_DIR / f"retrieval__{safe_name}__topk_{top_k}.json"


def _agent_route_report_path(dataset_name: str) -> Path:
    safe_name = _sanitize_segment(dataset_name)
    return REPORT_STORE_DIR / f"agent_route__{safe_name}.json"


def _agent_workflow_report_path(dataset_name: str) -> Path:
    safe_name = _sanitize_segment(dataset_name)
    return REPORT_STORE_DIR / f"agent_workflow__{safe_name}.json"


def persist_retrieval_report(dataset_name: str, top_k: int, report: Any) -> dict[str, Any]:
    payload = _report_payload(dataset_name=dataset_name, report=report, report_source="fresh")
    payload["top_k"] = top_k
    return _write_report(_retrieval_report_path(dataset_name, top_k), payload)


def load_latest_retrieval_report(dataset_name: str, top_k: int) -> dict[str, Any] | None:
    payload = _read_report(_retrieval_report_path(dataset_name, top_k))
    if payload is None:
        return None
    payload["report_source"] = "saved"
    return payload


def persist_agent_route_report(dataset_name: str, report: Any) -> dict[str, Any]:
    payload = _report_payload(dataset_name=dataset_name, report=report, report_source="fresh")
    return _write_report(_agent_route_report_path(dataset_name), payload)


def load_latest_agent_route_report(dataset_name: str) -> dict[str, Any] | None:
    payload = _read_report(_agent_route_report_path(dataset_name))
    if payload is None:
        return None
    payload["report_source"] = "saved"
    return payload


def persist_agent_workflow_report(dataset_name: str, report: Any) -> dict[str, Any]:
    payload = _report_payload(dataset_name=dataset_name, report=report, report_source="fresh")
    return _write_report(_agent_workflow_report_path(dataset_name), payload)


def load_latest_agent_workflow_report(dataset_name: str) -> dict[str, Any] | None:
    payload = _read_report(_agent_workflow_report_path(dataset_name))
    if payload is None:
        return None
    payload["report_source"] = "saved"
    return payload
