import type { FormEvent } from "react";

import type {
  AgentEvalDatasetInfo,
  AgentRouteEvalReportResponse,
  AgentWorkflowEvalReportResponse,
  EvalCaseFilter,
  EvalDatasetInfo,
  EvaluationMode,
  EvalReportResponse,
} from "../types";

function hasFilenames(dataset: EvalDatasetInfo | AgentEvalDatasetInfo): dataset is EvalDatasetInfo {
  return "filenames" in dataset;
}

type EvaluationViewProps = {
  evaluationMode: EvaluationMode;
  datasets: EvalDatasetInfo[];
  agentRouteDatasets: AgentEvalDatasetInfo[];
  agentWorkflowDatasets: AgentEvalDatasetInfo[];
  datasetName: string;
  evalTopK: number;
  evalResult: EvalReportResponse | null;
  agentRouteEvalResult: AgentRouteEvalReportResponse | null;
  agentWorkflowEvalResult: AgentWorkflowEvalReportResponse | null;
  evalError: string;
  evalBusy: boolean;
  evalCaseFilter: EvalCaseFilter;
  filteredEvalCases: EvalReportResponse["report"]["cases"];
  filteredAgentRouteCases: AgentRouteEvalReportResponse["report"]["cases"];
  filteredAgentWorkflowCases: AgentWorkflowEvalReportResponse["report"]["cases"];
  onRefreshDatasets: () => void;
  onChangeEvaluationMode: (mode: EvaluationMode) => void;
  onChangeDatasetName: (datasetName: string) => void;
  onChangeEvalTopK: (value: number) => void;
  onSubmitEvaluation: (event: FormEvent<HTMLFormElement>) => void;
  onChangeEvalCaseFilter: (filter: EvalCaseFilter) => void;
};

export function EvaluationView({
  evaluationMode,
  datasets,
  agentRouteDatasets,
  agentWorkflowDatasets,
  datasetName,
  evalTopK,
  evalResult,
  agentRouteEvalResult,
  agentWorkflowEvalResult,
  evalError,
  evalBusy,
  evalCaseFilter,
  filteredEvalCases,
  filteredAgentRouteCases,
  filteredAgentWorkflowCases,
  onRefreshDatasets,
  onChangeEvaluationMode,
  onChangeDatasetName,
  onChangeEvalTopK,
  onSubmitEvaluation,
  onChangeEvalCaseFilter,
}: EvaluationViewProps) {
  const visibleDatasets =
    evaluationMode === "retrieval"
      ? datasets
      : evaluationMode === "agent-route"
        ? agentRouteDatasets
        : agentWorkflowDatasets;

  const activeReport =
    evaluationMode === "retrieval"
      ? evalResult
      : evaluationMode === "agent-route"
        ? agentRouteEvalResult
        : agentWorkflowEvalResult;

  const modeCopy =
    evaluationMode === "retrieval"
      ? "Run curated retrieval benchmarks and inspect per-case ranking outcomes."
      : evaluationMode === "agent-route"
        ? "Evaluate whether the router selects the correct workflow path."
        : "Evaluate whether the unified agent workflow ends in the expected state.";
  const modeTitle =
    evaluationMode === "retrieval"
      ? "Benchmark Retrieval Quality"
      : evaluationMode === "agent-route"
        ? "Benchmark Routing Accuracy"
        : "Benchmark Agent Workflow Outcomes";

  return (
    <section className="panel-grid">
      <article className="panel panel-span view-banner">
        <div className="view-banner-content">
          <div>
            <span className="section-label">Evaluation Workspace</span>
            <h2 className="view-banner-title">{modeTitle}</h2>
            <p className="view-banner-copy">{modeCopy}</p>
          </div>
          <div className="view-banner-meta">
            <span>{visibleDatasets.length} datasets</span>
            <span>{evaluationMode}</span>
            <span>{datasetName || "no dataset"}</span>
            <span>top-k {evalTopK}</span>
            <span>{activeReport ? "report ready" : "report idle"}</span>
          </div>
        </div>
      </article>

      <article className="panel">
        <div className="panel-heading">
          <div>
            <h2>Evaluation Runner</h2>
            <p className="panel-intro">{modeCopy}</p>
          </div>
          <button type="button" className="ghost-button" onClick={onRefreshDatasets}>
            Refresh Datasets
          </button>
        </div>
        <form className="stack-form" onSubmit={onSubmitEvaluation}>
          <div className="filter-row">
            <button
              type="button"
              className={`filter-chip${evaluationMode === "retrieval" ? " active" : ""}`}
              onClick={() => onChangeEvaluationMode("retrieval")}
            >
              Retrieval
            </button>
            <button
              type="button"
              className={`filter-chip${evaluationMode === "agent-route" ? " active" : ""}`}
              onClick={() => onChangeEvaluationMode("agent-route")}
            >
              Agent Route
            </button>
            <button
              type="button"
              className={`filter-chip${evaluationMode === "agent-workflow" ? " active" : ""}`}
              onClick={() => onChangeEvaluationMode("agent-workflow")}
            >
              Agent Workflow
            </button>
          </div>
          <label>
            Dataset
            <select value={datasetName} onChange={(event) => onChangeDatasetName(event.target.value)}>
              {visibleDatasets.map((dataset) => (
                <option key={dataset.dataset_name} value={dataset.dataset_name}>
                  {dataset.dataset_name}
                </option>
              ))}
            </select>
          </label>
          {evaluationMode === "retrieval" && (
            <label>
              Top-K
              <input
                type="number"
                min={1}
                max={10}
                value={evalTopK}
                onChange={(event) => onChangeEvalTopK(Number(event.target.value))}
              />
            </label>
          )}
          <button type="submit" className="primary-button" disabled={evalBusy}>
            Run Evaluation
          </button>
        </form>
        {evalBusy && <p className="status">Running evaluation set...</p>}
        {evalError && <p className="error">{evalError}</p>}
        {visibleDatasets.length > 0 ? (
          <div className="dataset-list">
            {visibleDatasets.map((dataset) => (
              <article key={dataset.dataset_name} className="dataset-card">
                <strong>{dataset.dataset_name}</strong>
                <span>{dataset.case_count} cases</span>
                {hasFilenames(dataset) ? <small>{dataset.filenames.join(", ")}</small> : null}
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <strong>No evaluation datasets</strong>
            <p>Add datasets for the selected evaluation mode.</p>
          </div>
        )}
      </article>

      <article className="panel preview-panel">
        <div className="panel-heading">
          <div>
            <h2>Evaluation Report</h2>
            <p className="panel-intro">
              Compare benchmark summary metrics and inspect individual case behavior.
            </p>
          </div>
        </div>
        {evaluationMode === "retrieval" && evalResult ? (
          <>
            <div className="summary-strip">
              <div className="summary-card">
                <span className="trace-label">Total Cases</span>
                <strong>{evalResult.report.summary.total_cases}</strong>
              </div>
              <div className="summary-card">
                <span className="trace-label">Hit@{evalResult.report.top_k}</span>
                <strong>{evalResult.report.summary.hit_rate_at_k.toFixed(3)}</strong>
              </div>
              <div className="summary-card">
                <span className="trace-label">MRR</span>
                <strong>{evalResult.report.summary.mean_reciprocal_rank.toFixed(3)}</strong>
              </div>
            </div>
            <div className="panel-heading case-toolbar">
              <h3>Case Results</h3>
              <div className="filter-row">
                <button
                  type="button"
                  className={`filter-chip${evalCaseFilter === "all" ? " active" : ""}`}
                  onClick={() => onChangeEvalCaseFilter("all")}
                >
                  All
                </button>
                <button
                  type="button"
                  className={`filter-chip${evalCaseFilter === "hit" ? " active" : ""}`}
                  onClick={() => onChangeEvalCaseFilter("hit")}
                >
                  Hits
                </button>
                <button
                  type="button"
                  className={`filter-chip${evalCaseFilter === "miss" ? " active" : ""}`}
                  onClick={() => onChangeEvalCaseFilter("miss")}
                >
                  Misses
                </button>
              </div>
            </div>
            <div className="case-list">
              {filteredEvalCases.map((item) => (
                <article
                  key={item.case_id}
                  className={`case-card${item.hit_at_k ? " success" : " danger"}`}
                >
                  <header>
                    <strong>{item.case_id}</strong>
                    <span>{item.hit_at_k ? "hit" : "miss"}</span>
                  </header>
                  <p>{item.question}</p>
                  <div className="meta-row">
                    <span>RR {item.reciprocal_rank.toFixed(3)}</span>
                    <span>file {item.filename}</span>
                  </div>
                  <small>Expected: {item.expected_chunk_ids.join(", ")}</small>
                  <small>Retrieved: {item.retrieved_chunk_ids.join(", ")}</small>
                </article>
              ))}
            </div>
            {filteredEvalCases.length === 0 && (
              <p className="muted">
                No cases match the current filter. Switch to another view to inspect all benchmark
                cases again.
              </p>
            )}
          </>
        ) : evaluationMode === "agent-route" && agentRouteEvalResult ? (
          <>
            <div className="summary-strip">
              <div className="summary-card">
                <span className="trace-label">Total Cases</span>
                <strong>{agentRouteEvalResult.report.summary.total_cases}</strong>
              </div>
              <div className="summary-card">
                <span className="trace-label">Route Accuracy</span>
                <strong>{agentRouteEvalResult.report.summary.route_accuracy.toFixed(3)}</strong>
              </div>
              <div className="summary-card">
                <span className="trace-label">Matched Cases</span>
                <strong>
                  {agentRouteEvalResult.report.cases.filter((item) => item.matched).length}
                </strong>
              </div>
            </div>
            <div className="panel-heading case-toolbar">
              <h3>Case Results</h3>
              <div className="filter-row">
                <button
                  type="button"
                  className={`filter-chip${evalCaseFilter === "all" ? " active" : ""}`}
                  onClick={() => onChangeEvalCaseFilter("all")}
                >
                  All
                </button>
                <button
                  type="button"
                  className={`filter-chip${evalCaseFilter === "hit" ? " active" : ""}`}
                  onClick={() => onChangeEvalCaseFilter("hit")}
                >
                  Hits
                </button>
                <button
                  type="button"
                  className={`filter-chip${evalCaseFilter === "miss" ? " active" : ""}`}
                  onClick={() => onChangeEvalCaseFilter("miss")}
                >
                  Misses
                </button>
              </div>
            </div>
            <div className="case-list">
              {filteredAgentRouteCases.map((item) => (
                <article
                  key={item.case_id}
                  className={`case-card${item.matched ? " success" : " danger"}`}
                >
                  <header>
                    <strong>{item.case_id}</strong>
                    <span>{item.matched ? "matched" : "mismatch"}</span>
                  </header>
                  <p>{item.question}</p>
                  <div className="meta-row">
                    <span>expected {item.expected_route_type}</span>
                    <span>actual {item.actual_route_type}</span>
                    {item.filename ? <span>file {item.filename}</span> : null}
                  </div>
                  <small>{item.route_reason}</small>
                </article>
              ))}
            </div>
            {filteredAgentRouteCases.length === 0 && (
              <p className="muted">No cases match the current filter for this report.</p>
            )}
          </>
        ) : evaluationMode === "agent-workflow" && agentWorkflowEvalResult ? (
          <>
            <div className="summary-strip">
              <div className="summary-card">
                <span className="trace-label">Total Cases</span>
                <strong>{agentWorkflowEvalResult.report.summary.total_cases}</strong>
              </div>
              <div className="summary-card">
                <span className="trace-label">Workflow Accuracy</span>
                <strong>{agentWorkflowEvalResult.report.summary.workflow_accuracy.toFixed(3)}</strong>
              </div>
              <div className="summary-card">
                <span className="trace-label">Matched Cases</span>
                <strong>
                  {agentWorkflowEvalResult.report.cases.filter((item) => item.matched).length}
                </strong>
              </div>
            </div>
            <div className="panel-heading case-toolbar">
              <h3>Case Results</h3>
              <div className="filter-row">
                <button
                  type="button"
                  className={`filter-chip${evalCaseFilter === "all" ? " active" : ""}`}
                  onClick={() => onChangeEvalCaseFilter("all")}
                >
                  All
                </button>
                <button
                  type="button"
                  className={`filter-chip${evalCaseFilter === "hit" ? " active" : ""}`}
                  onClick={() => onChangeEvalCaseFilter("hit")}
                >
                  Hits
                </button>
                <button
                  type="button"
                  className={`filter-chip${evalCaseFilter === "miss" ? " active" : ""}`}
                  onClick={() => onChangeEvalCaseFilter("miss")}
                >
                  Misses
                </button>
              </div>
            </div>
            <div className="case-list">
              {filteredAgentWorkflowCases.map((item) => (
                <article
                  key={item.case_id}
                  className={`case-card${item.matched ? " success" : " danger"}`}
                >
                  <header>
                    <strong>{item.case_id}</strong>
                    <span>{item.matched ? "matched" : "mismatch"}</span>
                  </header>
                  <p>{item.question}</p>
                  <div className="meta-row">
                    <span>
                      route {item.expected_route_type} {"->"} {item.actual_route_type}
                    </span>
                    <span>
                      status {item.expected_workflow_status} {"->"} {item.actual_workflow_status}
                    </span>
                    {item.filename ? <span>file {item.filename}</span> : null}
                  </div>
                  <small>{item.route_reason}</small>
                </article>
              ))}
            </div>
            {filteredAgentWorkflowCases.length === 0 && (
              <p className="muted">No cases match the current filter for this report.</p>
            )}
          </>
        ) : (
          <div className="empty-state empty-state-large">
            <strong>No evaluation report yet</strong>
            <p>Select a dataset and run evaluation to view benchmark summaries and per-case outcomes.</p>
          </div>
        )}
      </article>
    </section>
  );
}


