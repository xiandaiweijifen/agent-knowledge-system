import json
from pathlib import Path

from app.schemas.evaluation import (
    AgentWorkflowEvalCase,
    AgentWorkflowEvalCaseResult,
    AgentWorkflowEvalReport,
    AgentWorkflowEvalSummary,
)
from app.schemas.evaluation_api import AgentWorkflowEvalDatasetInfo
from app.services.agent.orchestrator_service import orchestrate_agent_request

EVAL_DATA_DIR = Path("../data/eval")


def load_agent_workflow_eval_cases(dataset_path: Path) -> list[AgentWorkflowEvalCase]:
    """Load agent workflow evaluation cases from a JSON dataset."""
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    return [AgentWorkflowEvalCase.model_validate(item) for item in payload["cases"]]


def evaluate_agent_workflow_dataset(dataset_path: Path) -> AgentWorkflowEvalReport:
    """Evaluate final workflow behavior for the unified agent endpoint logic."""
    cases = load_agent_workflow_eval_cases(dataset_path)
    case_results = []

    for case in cases:
        response = orchestrate_agent_request(
            question=case.question,
            filename=case.filename,
            top_k=case.top_k,
        )
        matched = (
            response.route.route_type == case.expected_route_type
            and response.workflow_status == case.expected_workflow_status
        )
        case_results.append(
            AgentWorkflowEvalCaseResult(
                case_id=case.case_id,
                question=case.question,
                filename=case.filename,
                expected_route_type=case.expected_route_type,
                actual_route_type=response.route.route_type,
                expected_workflow_status=case.expected_workflow_status,
                actual_workflow_status=response.workflow_status,
                route_reason=response.route.route_reason,
                matched=matched,
            )
        )

    total_cases = len(case_results)
    matched_count = sum(1 for case in case_results if case.matched)

    return AgentWorkflowEvalReport(
        summary=AgentWorkflowEvalSummary(
            total_cases=total_cases,
            workflow_accuracy=round(matched_count / total_cases, 6) if total_cases else 0.0,
        ),
        cases=case_results,
    )


def evaluate_named_agent_workflow_dataset(dataset_name: str) -> AgentWorkflowEvalReport:
    """Evaluate workflow behavior for a named local dataset."""
    normalized_name = dataset_name.strip()

    if not normalized_name:
        raise ValueError("dataset_name_must_not_be_empty")

    dataset_path = EVAL_DATA_DIR / normalized_name

    if not dataset_path.exists() or not dataset_path.is_file():
        raise FileNotFoundError(dataset_name)

    return evaluate_agent_workflow_dataset(dataset_path=dataset_path)


def list_agent_workflow_datasets() -> list[AgentWorkflowEvalDatasetInfo]:
    """List available agent workflow evaluation datasets."""
    datasets = []

    if not EVAL_DATA_DIR.exists():
        return datasets

    for dataset_path in sorted(EVAL_DATA_DIR.glob("*_workflow_eval.json")):
        cases = load_agent_workflow_eval_cases(dataset_path)
        datasets.append(
            AgentWorkflowEvalDatasetInfo(
                dataset_name=dataset_path.name,
                case_count=len(cases),
            )
        )

    return datasets
