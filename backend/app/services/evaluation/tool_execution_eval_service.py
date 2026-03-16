import json
from pathlib import Path

from app.core.config import DATA_ROOT
from app.schemas.evaluation import (
    ToolExecutionEvalCase,
    ToolExecutionEvalCaseResult,
    ToolExecutionEvalReport,
    ToolExecutionEvalSummary,
)
from app.schemas.evaluation_api import ToolExecutionEvalDatasetInfo
from app.schemas.tools import ToolExecutionRequest
from app.services.agent.tool_service import execute_tool_request, plan_tool_request

EVAL_DATA_DIR = DATA_ROOT / "eval"


def load_tool_execution_eval_cases(dataset_path: Path) -> list[ToolExecutionEvalCase]:
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    return [ToolExecutionEvalCase.model_validate(item) for item in payload["cases"]]


def evaluate_tool_execution_dataset(dataset_path: Path) -> ToolExecutionEvalReport:
    cases = load_tool_execution_eval_cases(dataset_path)
    case_results: list[ToolExecutionEvalCaseResult] = []

    for case in cases:
        tool_plan = plan_tool_request(case.question)
        tool_execution = execute_tool_request(
            ToolExecutionRequest(
                tool_name=tool_plan.tool_name,
                action=tool_plan.action,
                target=tool_plan.target,
                arguments=tool_plan.arguments,
            )
        )

        argument_matches = {
            key: tool_plan.arguments.get(key) == value
            for key, value in case.expected_arguments.items()
        }
        output_matches = {
            key: tool_execution.output.get(key) == value
            for key, value in case.expected_output.items()
        }
        output_key_matches = {
            key: key in tool_execution.output for key in case.expected_output_keys
        }

        matched = (
            tool_plan.tool_name == case.expected_tool_name
            and tool_plan.action == case.expected_action
            and tool_execution.execution_status == case.expected_execution_status
            and all(argument_matches.values())
            and all(output_matches.values())
            and all(output_key_matches.values())
        )

        case_results.append(
            ToolExecutionEvalCaseResult(
                case_id=case.case_id,
                question=case.question,
                expected_tool_name=case.expected_tool_name,
                actual_tool_name=tool_plan.tool_name,
                expected_action=case.expected_action,
                actual_action=tool_plan.action,
                expected_execution_status=case.expected_execution_status,
                actual_execution_status=tool_execution.execution_status,
                matched=matched,
                argument_matches=argument_matches,
                output_matches=output_matches,
                output_key_matches=output_key_matches,
            )
        )

    total_cases = len(case_results)
    matched_count = sum(1 for case in case_results if case.matched)

    return ToolExecutionEvalReport(
        summary=ToolExecutionEvalSummary(
            total_cases=total_cases,
            tool_accuracy=round(matched_count / total_cases, 6) if total_cases else 0.0,
        ),
        cases=case_results,
    )


def evaluate_named_tool_execution_dataset(dataset_name: str) -> ToolExecutionEvalReport:
    normalized_name = dataset_name.strip()

    if not normalized_name:
        raise ValueError("dataset_name_must_not_be_empty")

    dataset_path = EVAL_DATA_DIR / normalized_name
    if not dataset_path.exists() or not dataset_path.is_file():
        raise FileNotFoundError(dataset_name)

    return evaluate_tool_execution_dataset(dataset_path)


def list_tool_execution_datasets() -> list[ToolExecutionEvalDatasetInfo]:
    datasets: list[ToolExecutionEvalDatasetInfo] = []

    if not EVAL_DATA_DIR.exists():
        return datasets

    for dataset_path in sorted(EVAL_DATA_DIR.glob("*_tool_execution_eval.json")):
        cases = load_tool_execution_eval_cases(dataset_path)
        datasets.append(
            ToolExecutionEvalDatasetInfo(
                dataset_name=dataset_path.name,
                case_count=len(cases),
            )
        )

    return datasets
