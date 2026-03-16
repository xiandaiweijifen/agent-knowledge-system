import json
from pathlib import Path

from app.core.config import DATA_ROOT
from app.schemas.evaluation import (
    AgentRouteEvalCase,
    AgentRouteEvalCaseResult,
    AgentRouteEvalReport,
    AgentRouteEvalSummary,
)
from app.schemas.evaluation_api import AgentRouteEvalDatasetInfo
from app.services.agent.router_service import route_request

EVAL_DATA_DIR = DATA_ROOT / "eval"


def load_agent_route_eval_cases(dataset_path: Path) -> list[AgentRouteEvalCase]:
    """Load agent routing evaluation cases from a JSON dataset."""
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    return [AgentRouteEvalCase.model_validate(item) for item in payload["cases"]]


def evaluate_agent_route_dataset(dataset_path: Path) -> AgentRouteEvalReport:
    """Evaluate route classification accuracy on a local dataset."""
    cases = load_agent_route_eval_cases(dataset_path)
    case_results = []

    for case in cases:
        decision = route_request(
            question=case.question,
            filename=case.filename,
        )
        matched = decision.route_type == case.expected_route_type
        case_results.append(
            AgentRouteEvalCaseResult(
                case_id=case.case_id,
                question=case.question,
                filename=case.filename,
                expected_route_type=case.expected_route_type,
                actual_route_type=decision.route_type,
                route_reason=decision.route_reason,
                matched=matched,
            )
        )

    total_cases = len(case_results)
    matched_count = sum(1 for case in case_results if case.matched)

    return AgentRouteEvalReport(
        summary=AgentRouteEvalSummary(
            total_cases=total_cases,
            route_accuracy=round(matched_count / total_cases, 6) if total_cases else 0.0,
        ),
        cases=case_results,
    )


def evaluate_named_agent_route_dataset(dataset_name: str) -> AgentRouteEvalReport:
    """Evaluate route classification for a named local dataset."""
    normalized_name = dataset_name.strip()

    if not normalized_name:
        raise ValueError("dataset_name_must_not_be_empty")

    dataset_path = EVAL_DATA_DIR / normalized_name

    if not dataset_path.exists() or not dataset_path.is_file():
        raise FileNotFoundError(dataset_name)

    return evaluate_agent_route_dataset(dataset_path=dataset_path)


def list_agent_route_datasets() -> list[AgentRouteEvalDatasetInfo]:
    """List available agent routing evaluation datasets."""
    datasets = []

    if not EVAL_DATA_DIR.exists():
        return datasets

    for dataset_path in sorted(EVAL_DATA_DIR.glob("*_route_eval.json")):
        cases = load_agent_route_eval_cases(dataset_path)
        datasets.append(
            AgentRouteEvalDatasetInfo(
                dataset_name=dataset_path.name,
                case_count=len(cases),
            )
        )

    return datasets
