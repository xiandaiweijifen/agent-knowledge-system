import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EvaluationView } from "./EvaluationView";

describe("EvaluationView", () => {
  it("renders overview metrics before detailed evaluation reports", () => {
    render(
      <EvaluationView
        locale="en"
        evaluationMode="retrieval"
        evaluationOverview={{
          generated_at: "2026-03-17T00:00:00+00:00",
          cache_status: "cached",
          retrieval: {
            dataset_count: 2,
            total_cases: 12,
            mean_hit_rate_at_k: 0.875,
            mean_reciprocal_rank: 0.71,
            best_dataset_name: "rag_overview_retrieval_eval.json",
            best_hit_rate_at_k: 1,
          },
          workflow: {
            total_run_count: 20,
            completed_run_count: 12,
            clarification_required_run_count: 3,
            failed_run_count: 5,
            completion_rate: 0.6,
            clarification_rate: 0.15,
            failed_rate: 0.25,
          },
          recovery: {
            recovered_run_count: 6,
            recovered_completed_run_count: 5,
            recovery_success_rate: 0.833,
            average_recovery_depth: 1.33,
            resume_from_failed_step_count: 3,
            manual_retrigger_count: 2,
            clarification_recovery_count: 1,
          },
        }}
        datasets={[
          {
            dataset_name: "rag_overview_retrieval_eval.json",
            case_count: 6,
            filenames: ["rag_overview.md"],
          },
        ]}
        agentRouteDatasets={[]}
        agentWorkflowDatasets={[]}
        datasetName="rag_overview_retrieval_eval.json"
        evalTopK={3}
        evalResult={null}
        agentRouteEvalResult={null}
        agentWorkflowEvalResult={null}
        evalError=""
        evalBusy={false}
        evalCaseFilter="all"
        filteredEvalCases={[]}
        filteredAgentRouteCases={[]}
        filteredAgentWorkflowCases={[]}
        onRefreshDatasets={vi.fn()}
        onChangeEvaluationMode={vi.fn()}
        onChangeDatasetName={vi.fn()}
        onChangeEvalTopK={vi.fn()}
        onSubmitEvaluation={vi.fn()}
        onChangeEvalCaseFilter={vi.fn()}
      />,
    );

    expect(screen.getByText("Evaluation Overview")).toBeInTheDocument();
    expect(screen.getByText("Retrieval Overview")).toBeInTheDocument();
    expect(screen.getByText("Workflow Overview")).toBeInTheDocument();
    expect(screen.getByText("Recovery Overview")).toBeInTheDocument();
    expect(screen.getByText("Mean Hit@K")).toBeInTheDocument();
    expect(screen.getByText("Recovery Success Rate")).toBeInTheDocument();
    expect(screen.getByText("rag_overview_retrieval_eval.json (1.000)")).toBeInTheDocument();
    expect(screen.getByText((content) => content.includes("Cache Status: Cached"))).toBeInTheDocument();
    expect(screen.getByText((content) => content.includes("failed-step 3"))).toBeInTheDocument();
    expect(screen.getByText((content) => content.includes("manual 2"))).toBeInTheDocument();
    expect(screen.getByText((content) => content.includes("clarification 1"))).toBeInTheDocument();
  });
});
