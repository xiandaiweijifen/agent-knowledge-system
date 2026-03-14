import type { FormEvent } from "react";

import type { EvalCaseFilter, EvalDatasetInfo, EvalReportResponse } from "../types";

type EvaluationViewProps = {
  datasets: EvalDatasetInfo[];
  datasetName: string;
  evalTopK: number;
  evalResult: EvalReportResponse | null;
  evalError: string;
  evalBusy: boolean;
  evalCaseFilter: EvalCaseFilter;
  filteredEvalCases: EvalReportResponse["report"]["cases"];
  onRefreshDatasets: () => void;
  onChangeDatasetName: (datasetName: string) => void;
  onChangeEvalTopK: (value: number) => void;
  onSubmitEvaluation: (event: FormEvent<HTMLFormElement>) => void;
  onChangeEvalCaseFilter: (filter: EvalCaseFilter) => void;
};

export function EvaluationView({
  datasets,
  datasetName,
  evalTopK,
  evalResult,
  evalError,
  evalBusy,
  evalCaseFilter,
  filteredEvalCases,
  onRefreshDatasets,
  onChangeDatasetName,
  onChangeEvalTopK,
  onSubmitEvaluation,
  onChangeEvalCaseFilter,
}: EvaluationViewProps) {
  return (
    <section className="panel-grid">
      <article className="panel panel-span view-banner">
        <div className="view-banner-content">
          <div>
            <span className="section-label">Evaluation Workspace</span>
            <h2 className="view-banner-title">Benchmark Retrieval Quality</h2>
            <p className="view-banner-copy">
              Run curated datasets, inspect summary metrics, and review per-case ranking outcomes.
            </p>
          </div>
          <div className="view-banner-meta">
            <span>{datasets.length} datasets</span>
            <span>{datasetName || "no dataset"}</span>
            <span>top-k {evalTopK}</span>
            <span>{evalResult ? "report ready" : "report idle"}</span>
          </div>
        </div>
      </article>

      <article className="panel">
        <div className="panel-heading">
          <div>
            <h2>Evaluation Runner</h2>
            <p className="panel-intro">
              Run curated retrieval benchmarks and inspect per-case ranking outcomes.
            </p>
          </div>
          <button type="button" className="ghost-button" onClick={onRefreshDatasets}>
            Refresh Datasets
          </button>
        </div>
        <form className="stack-form" onSubmit={onSubmitEvaluation}>
          <label>
            Dataset
            <select value={datasetName} onChange={(event) => onChangeDatasetName(event.target.value)}>
              {datasets.map((dataset) => (
                <option key={dataset.dataset_name} value={dataset.dataset_name}>
                  {dataset.dataset_name}
                </option>
              ))}
            </select>
          </label>
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
          <button type="submit" className="primary-button" disabled={evalBusy}>
            Run Evaluation
          </button>
        </form>
        {evalBusy && <p className="status">Benchmarking retrieval set...</p>}
        {evalError && <p className="error">{evalError}</p>}
        {datasets.length > 0 ? (
          <div className="dataset-list">
            {datasets.map((dataset) => (
              <article key={dataset.dataset_name} className="dataset-card">
                <strong>{dataset.dataset_name}</strong>
                <span>{dataset.case_count} cases</span>
                <small>{dataset.filenames.join(", ")}</small>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <strong>No evaluation datasets</strong>
            <p>Add a retrieval evaluation dataset to benchmark query quality.</p>
          </div>
        )}
      </article>

      <article className="panel preview-panel">
        <div className="panel-heading">
          <div>
            <h2>Evaluation Report</h2>
            <p className="panel-intro">
              Compare benchmark hit rate, reciprocal rank, and individual case behavior.
            </p>
          </div>
        </div>
        {evalResult ? (
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
