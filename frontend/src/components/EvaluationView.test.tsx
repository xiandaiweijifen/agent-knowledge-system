import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EvaluationView } from "./EvaluationView";

describe("EvaluationView", () => {
  it("renders overview metrics before detailed evaluation reports", () => {
    const onExportBundle = vi.fn();

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
        evaluationMetricsSummary={{
          generated_at: "2026-03-17T00:00:00+00:00",
          cache_status: "cached",
          highlights: [
            {
              label: "Workflow Completion",
              value: "63.7%",
              detail: "107/168 runs completed.",
            },
          ],
          sections: [
            {
              title: "Showcase Retrieval Benchmark",
              dataset_name: "agent_workflow_retrieval_eval.json",
              metric_name: "hit_rate_at_k",
              metric_value: 1,
              formatted_value: "1.000",
              detail: "MRR 0.917 at top-3.",
            },
          ],
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
        toolExecutionDatasets={[]}
        datasetName="rag_overview_retrieval_eval.json"
        evalTopK={3}
        evaluationHistory={[
          {
            dataset_name: "rag_overview_retrieval_eval.json",
            saved_at: "2026-03-17T01:30:00+00:00",
            report_source: "saved",
            top_k: 3,
            primary_metric_name: "hit_rate_at_k",
            primary_metric_value: 0.875,
            case_count: 6,
          },
          {
            dataset_name: "rag_overview_retrieval_eval.json",
            saved_at: "2026-03-16T23:30:00+00:00",
            report_source: "saved",
            top_k: 3,
            primary_metric_name: "hit_rate_at_k",
            primary_metric_value: 0.75,
            case_count: 6,
          },
        ]}
        evalResult={{
          dataset_name: "rag_overview_retrieval_eval.json",
          saved_at: "2026-03-17T01:30:00+00:00",
          report_source: "saved",
          report: {
            top_k: 3,
            summary: {
              total_cases: 6,
              hit_rate_at_k: 0.875,
              mean_reciprocal_rank: 0.71,
            },
            cases: [],
          },
        }}
        agentRouteEvalResult={null}
        agentWorkflowEvalResult={null}
        toolExecutionEvalResult={null}
        evalError=""
        evalBusy={false}
        evalCaseFilter="all"
        filteredEvalCases={[]}
        filteredAgentRouteCases={[]}
        filteredAgentWorkflowCases={[]}
        exportBusy={false}
        onRefreshDatasets={vi.fn()}
        onExportBundle={onExportBundle}
        onChangeEvaluationMode={vi.fn()}
        onChangeDatasetName={vi.fn()}
        onChangeEvalTopK={vi.fn()}
        onSubmitEvaluation={vi.fn()}
        onChangeEvalCaseFilter={vi.fn()}
      />,
    );

    expect(screen.getByText("Evaluation Overview")).toBeInTheDocument();
    expect(screen.getByText("Evaluation Highlights")).toBeInTheDocument();
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
    expect(screen.getByText("Latest Saved Result")).toBeInTheDocument();
    expect(screen.getByText((content) => content.includes("Report Source: Saved"))).toBeInTheDocument();
    expect(screen.getByText((content) => content.includes("Vs Previous: Improved 0.125"))).toBeInTheDocument();
    expect(screen.getByText("Recent Evaluation History")).toBeInTheDocument();
    expect(screen.getByText("Workflow Completion")).toBeInTheDocument();
    expect(screen.getByText("Showcase Benchmark")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Export Evaluation Bundle" }));
    expect(onExportBundle).toHaveBeenCalledTimes(1);
  });
});
