import type { FormEvent } from "react";

import type {
  AgentEvalDatasetInfo,
  AgentRouteEvalReportResponse,
  AgentWorkflowEvalReportResponse,
  EvalCaseFilter,
  EvalDatasetInfo,
  EvaluationOverviewResponse,
  EvaluationMode,
  EvalReportResponse,
  Locale,
} from "../types";

function hasFilenames(dataset: EvalDatasetInfo | AgentEvalDatasetInfo): dataset is EvalDatasetInfo {
  return "filenames" in dataset;
}

type EvaluationViewProps = {
  locale: Locale;
  evaluationMode: EvaluationMode;
  evaluationOverview: EvaluationOverviewResponse | null;
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
  locale,
  evaluationMode,
  evaluationOverview,
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
  const copy =
    locale === "zh"
      ? {
          workspace: "评测工作台",
          overview: "评测总览",
          overviewCopy: "汇总当前检索、workflow 与恢复能力的关键指标，便于快速评估系统成熟度。",
          retrievalOverview: "检索概览",
          workflowOverview: "工作流概览",
          recoveryOverview: "恢复概览",
          datasetCount: "数据集数",
          totalCasesOverview: "总 Case 数",
          meanHitRate: "平均 Hit@K",
          meanMrr: "平均 MRR",
          bestDataset: "最佳数据集",
          totalRuns: "总运行数",
          completionRate: "完成率",
          clarificationRate: "澄清率",
          failedRate: "失败率",
          recoveredRuns: "恢复运行数",
          recoverySuccessRate: "恢复成功率",
          averageRecoveryDepth: "平均恢复深度",
          recoveryMix: "恢复动作分布",
          generatedAt: "生成时间",
          unavailableMetric: "暂无数据",
          retrievalCopy: "运行预设检索基准并检查逐条 case 的排序结果。",
          routeCopy: "评估路由器是否选择了正确的工作流路径。",
          workflowCopy: "评估统一 agent workflow 是否落到预期状态。",
          retrievalTitle: "检索质量基准",
          routeTitle: "路由准确率基准",
          workflowTitle: "Agent Workflow 结果基准",
          datasets: "数据集",
          topKSummary: "top-k",
          noDataset: "未选择数据集",
          reportReady: "报告已就绪",
          reportIdle: "报告未生成",
          runner: "评测执行器",
          refreshDatasets: "刷新数据集",
          dataset: "数据集",
          topK: "Top-K",
          runEvaluation: "运行评测",
          runningEvaluation: "正在运行评测...",
          noDatasets: "暂无评测数据集",
          noDatasetsCopy: "请为当前评测模式添加数据集。",
          report: "评测报告",
          reportCopy: "对比基准汇总指标，并检查单个 case 的表现。",
          totalCases: "总 Case 数",
          routeAccuracy: "路由准确率",
          workflowAccuracy: "工作流准确率",
          matchedCases: "匹配 Case",
          hit: "命中",
          hits: "命中",
          miss: "未命中",
          misses: "未命中",
          all: "全部",
          caseResults: "Case 结果",
          reciprocalRank: "RR",
          file: "文件",
          expected: "预期",
          retrieved: "检索到",
          matched: "匹配",
          mismatch: "不匹配",
          routeLabel: "路由",
          statusLabel: "状态",
          retrievalMode: "检索",
          routeMode: "Agent 路由",
          workflowMode: "Agent 工作流",
          cases: "条 case",
          actual: "实际",
          hitAt: "Hit@",
          noCases: "当前过滤条件下没有 case。",
          noReport: "暂无评测报告",
          noReportCopy: "选择数据集并运行评测后，可查看汇总指标和逐条 case 结果。",
        }
      : {
          workspace: "Evaluation Workspace",
          overview: "Evaluation Overview",
          overviewCopy:
            "Summarize retrieval, workflow, and recovery health in one place before drilling into individual benchmark suites.",
          retrievalOverview: "Retrieval Overview",
          workflowOverview: "Workflow Overview",
          recoveryOverview: "Recovery Overview",
          datasetCount: "Dataset Count",
          totalCasesOverview: "Total Cases",
          meanHitRate: "Mean Hit@K",
          meanMrr: "Mean MRR",
          bestDataset: "Best Dataset",
          totalRuns: "Total Runs",
          completionRate: "Completion Rate",
          clarificationRate: "Clarification Rate",
          failedRate: "Failed Rate",
          recoveredRuns: "Recovered Runs",
          recoverySuccessRate: "Recovery Success Rate",
          averageRecoveryDepth: "Average Recovery Depth",
          recoveryMix: "Recovery Action Mix",
          generatedAt: "Generated At",
          unavailableMetric: "Unavailable",
          retrievalCopy: "Run curated retrieval benchmarks and inspect per-case ranking outcomes.",
          routeCopy: "Evaluate whether the router selects the correct workflow path.",
          workflowCopy: "Evaluate whether the unified agent workflow ends in the expected state.",
          retrievalTitle: "Benchmark Retrieval Quality",
          routeTitle: "Benchmark Routing Accuracy",
          workflowTitle: "Benchmark Agent Workflow Outcomes",
          datasets: "datasets",
          topKSummary: "top-k",
          noDataset: "no dataset",
          reportReady: "report ready",
          reportIdle: "report idle",
          runner: "Evaluation Runner",
          refreshDatasets: "Refresh Datasets",
          dataset: "Dataset",
          topK: "Top-K",
          runEvaluation: "Run Evaluation",
          runningEvaluation: "Running evaluation set...",
          noDatasets: "No evaluation datasets",
          noDatasetsCopy: "Add datasets for the selected evaluation mode.",
          report: "Evaluation Report",
          reportCopy: "Compare benchmark summary metrics and inspect individual case behavior.",
          totalCases: "Total Cases",
          routeAccuracy: "Route Accuracy",
          workflowAccuracy: "Workflow Accuracy",
          matchedCases: "Matched Cases",
          hit: "hit",
          hits: "Hits",
          miss: "miss",
          misses: "Misses",
          all: "All",
          caseResults: "Case Results",
          reciprocalRank: "RR",
          file: "file",
          expected: "Expected",
          retrieved: "Retrieved",
          matched: "matched",
          mismatch: "mismatch",
          routeLabel: "route",
          statusLabel: "status",
          retrievalMode: "Retrieval",
          routeMode: "Agent Route",
          workflowMode: "Agent Workflow",
          cases: "cases",
          actual: "actual",
          hitAt: "Hit@",
          noCases: "No cases match the current filter for this report.",
          noReport: "No evaluation report yet",
          noReportCopy:
            "Select a dataset and run evaluation to view benchmark summaries and per-case outcomes.",
        };
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
      ? copy.retrievalCopy
      : evaluationMode === "agent-route"
        ? copy.routeCopy
        : copy.workflowCopy;
  const modeTitle =
    evaluationMode === "retrieval"
      ? copy.retrievalTitle
      : evaluationMode === "agent-route"
        ? copy.routeTitle
        : copy.workflowTitle;
  const overviewBestDataset = evaluationOverview?.retrieval.best_dataset_name
    ? `${evaluationOverview.retrieval.best_dataset_name} (${evaluationOverview.retrieval.best_hit_rate_at_k.toFixed(3)})`
    : copy.unavailableMetric;
  const overviewGeneratedAt = evaluationOverview?.generated_at
    ? new Date(evaluationOverview.generated_at).toLocaleString(locale === "zh" ? "zh-CN" : "en-US")
    : copy.unavailableMetric;

  return (
    <section className="panel-grid">
      <article className="panel panel-span view-banner">
        <div className="view-banner-content">
          <div>
            <span className="section-label">{copy.workspace}</span>
            <h2 className="view-banner-title">{modeTitle}</h2>
            <p className="view-banner-copy">{modeCopy}</p>
          </div>
          <div className="view-banner-meta">
            <span>{visibleDatasets.length} {copy.datasets}</span>
            <span>
              {evaluationMode === "retrieval"
                ? copy.retrievalMode
                : evaluationMode === "agent-route"
                  ? copy.routeMode
                  : copy.workflowMode}
            </span>
            <span>{datasetName || copy.noDataset}</span>
            <span>{copy.topKSummary} {evalTopK}</span>
            <span>{activeReport ? copy.reportReady : copy.reportIdle}</span>
          </div>
        </div>
      </article>

      <article className="panel panel-span">
        <div className="panel-heading">
          <div>
            <h2>{copy.overview}</h2>
            <p className="panel-intro">{copy.overviewCopy}</p>
          </div>
          <span className="status-pill">
            <span>{copy.generatedAt}</span>
            <strong>{overviewGeneratedAt}</strong>
          </span>
        </div>
        {evaluationOverview ? (
          <div className="overview-grid">
            <section className="subsection-card">
              <span className="section-label">{copy.retrievalOverview}</span>
              <div className="summary-strip overview-summary-strip">
                <div className="summary-card">
                  <span className="trace-label">{copy.datasetCount}</span>
                  <strong>{evaluationOverview.retrieval.dataset_count}</strong>
                </div>
                <div className="summary-card">
                  <span className="trace-label">{copy.totalCasesOverview}</span>
                  <strong>{evaluationOverview.retrieval.total_cases}</strong>
                </div>
                <div className="summary-card">
                  <span className="trace-label">{copy.meanHitRate}</span>
                  <strong>{evaluationOverview.retrieval.mean_hit_rate_at_k.toFixed(3)}</strong>
                </div>
                <div className="summary-card">
                  <span className="trace-label">{copy.meanMrr}</span>
                  <strong>{evaluationOverview.retrieval.mean_reciprocal_rank.toFixed(3)}</strong>
                </div>
              </div>
              <div className="preview-meta">
                <span className="trace-label">{copy.bestDataset}</span>
                <strong>{overviewBestDataset}</strong>
              </div>
            </section>

            <section className="subsection-card">
              <span className="section-label">{copy.workflowOverview}</span>
              <div className="summary-strip overview-summary-strip">
                <div className="summary-card">
                  <span className="trace-label">{copy.totalRuns}</span>
                  <strong>{evaluationOverview.workflow.total_run_count}</strong>
                </div>
                <div className="summary-card">
                  <span className="trace-label">{copy.completionRate}</span>
                  <strong>{evaluationOverview.workflow.completion_rate.toFixed(3)}</strong>
                </div>
                <div className="summary-card">
                  <span className="trace-label">{copy.clarificationRate}</span>
                  <strong>{evaluationOverview.workflow.clarification_rate.toFixed(3)}</strong>
                </div>
                <div className="summary-card">
                  <span className="trace-label">{copy.failedRate}</span>
                  <strong>{evaluationOverview.workflow.failed_rate.toFixed(3)}</strong>
                </div>
              </div>
            </section>

            <section className="subsection-card">
              <span className="section-label">{copy.recoveryOverview}</span>
              <div className="summary-strip overview-summary-strip">
                <div className="summary-card">
                  <span className="trace-label">{copy.recoveredRuns}</span>
                  <strong>{evaluationOverview.recovery.recovered_run_count}</strong>
                </div>
                <div className="summary-card">
                  <span className="trace-label">{copy.recoverySuccessRate}</span>
                  <strong>{evaluationOverview.recovery.recovery_success_rate.toFixed(3)}</strong>
                </div>
                <div className="summary-card">
                  <span className="trace-label">{copy.averageRecoveryDepth}</span>
                  <strong>{evaluationOverview.recovery.average_recovery_depth.toFixed(2)}</strong>
                </div>
              </div>
              <div className="pill-strip">
                <span className="meta-pill">
                  {copy.recoveryMix}: failed-step {evaluationOverview.recovery.resume_from_failed_step_count}
                </span>
                <span className="meta-pill">
                  manual {evaluationOverview.recovery.manual_retrigger_count}
                </span>
                <span className="meta-pill">
                  clarification {evaluationOverview.recovery.clarification_recovery_count}
                </span>
              </div>
            </section>
          </div>
        ) : (
          <div className="empty-state">
            <strong>{copy.overview}</strong>
            <p>{copy.unavailableMetric}</p>
          </div>
        )}
      </article>

      <article className="panel">
        <div className="panel-heading">
          <div>
            <h2>{copy.runner}</h2>
            <p className="panel-intro">{modeCopy}</p>
          </div>
          <button type="button" className="ghost-button" onClick={onRefreshDatasets}>
            {copy.refreshDatasets}
          </button>
        </div>
        <form className="stack-form" onSubmit={onSubmitEvaluation}>
          <div className="filter-row">
            <button
              type="button"
              className={`filter-chip${evaluationMode === "retrieval" ? " active" : ""}`}
              onClick={() => onChangeEvaluationMode("retrieval")}
            >
              {copy.retrievalMode}
            </button>
            <button
              type="button"
              className={`filter-chip${evaluationMode === "agent-route" ? " active" : ""}`}
              onClick={() => onChangeEvaluationMode("agent-route")}
            >
              {copy.routeMode}
            </button>
            <button
              type="button"
              className={`filter-chip${evaluationMode === "agent-workflow" ? " active" : ""}`}
              onClick={() => onChangeEvaluationMode("agent-workflow")}
            >
              {copy.workflowMode}
            </button>
          </div>
          <label>
            {copy.dataset}
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
              {copy.topK}
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
            {copy.runEvaluation}
          </button>
        </form>
        {evalBusy && <p className="status">{copy.runningEvaluation}</p>}
        {evalError && <p className="error">{evalError}</p>}
        {visibleDatasets.length > 0 ? (
          <div className="dataset-list">
            {visibleDatasets.map((dataset) => (
              <article key={dataset.dataset_name} className="dataset-card">
                <strong>{dataset.dataset_name}</strong>
                <span>{dataset.case_count} {copy.cases}</span>
                {hasFilenames(dataset) ? <small>{dataset.filenames.join(", ")}</small> : null}
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <strong>{copy.noDatasets}</strong>
            <p>{copy.noDatasetsCopy}</p>
          </div>
        )}
      </article>

      <article className="panel preview-panel">
        <div className="panel-heading">
          <div>
            <h2>{copy.report}</h2>
            <p className="panel-intro">{copy.reportCopy}</p>
          </div>
        </div>
        {evaluationMode === "retrieval" && evalResult ? (
          <>
            <div className="summary-strip">
              <div className="summary-card">
                <span className="trace-label">{copy.totalCases}</span>
                <strong>{evalResult.report.summary.total_cases}</strong>
              </div>
              <div className="summary-card">
                <span className="trace-label">{copy.hitAt}{evalResult.report.top_k}</span>
                <strong>{evalResult.report.summary.hit_rate_at_k.toFixed(3)}</strong>
              </div>
              <div className="summary-card">
                <span className="trace-label">MRR</span>
                <strong>{evalResult.report.summary.mean_reciprocal_rank.toFixed(3)}</strong>
              </div>
            </div>
            <div className="panel-heading case-toolbar">
              <h3>{copy.caseResults}</h3>
              <div className="filter-row">
                <button
                  type="button"
                  className={`filter-chip${evalCaseFilter === "all" ? " active" : ""}`}
                  onClick={() => onChangeEvalCaseFilter("all")}
                >
                  {copy.all}
                </button>
                <button
                  type="button"
                  className={`filter-chip${evalCaseFilter === "hit" ? " active" : ""}`}
                  onClick={() => onChangeEvalCaseFilter("hit")}
                >
                  {copy.hits}
                </button>
                <button
                  type="button"
                  className={`filter-chip${evalCaseFilter === "miss" ? " active" : ""}`}
                  onClick={() => onChangeEvalCaseFilter("miss")}
                >
                  {copy.misses}
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
                    <span>{item.hit_at_k ? copy.hit : copy.miss}</span>
                  </header>
                  <p>{item.question}</p>
                  <div className="meta-row">
                    <span>{copy.reciprocalRank} {item.reciprocal_rank.toFixed(3)}</span>
                    <span>{copy.file} {item.filename}</span>
                  </div>
                  <small>{copy.expected}: {item.expected_chunk_ids.join(", ")}</small>
                  <small>{copy.retrieved}: {item.retrieved_chunk_ids.join(", ")}</small>
                </article>
              ))}
            </div>
            {filteredEvalCases.length === 0 && (
              <p className="muted">{copy.noCases}</p>
            )}
          </>
        ) : evaluationMode === "agent-route" && agentRouteEvalResult ? (
          <>
            <div className="summary-strip">
              <div className="summary-card">
                <span className="trace-label">{copy.totalCases}</span>
                <strong>{agentRouteEvalResult.report.summary.total_cases}</strong>
              </div>
              <div className="summary-card">
                <span className="trace-label">{copy.routeAccuracy}</span>
                <strong>{agentRouteEvalResult.report.summary.route_accuracy.toFixed(3)}</strong>
              </div>
              <div className="summary-card">
                <span className="trace-label">{copy.matchedCases}</span>
                <strong>
                  {agentRouteEvalResult.report.cases.filter((item) => item.matched).length}
                </strong>
              </div>
            </div>
            <div className="panel-heading case-toolbar">
              <h3>{copy.caseResults}</h3>
              <div className="filter-row">
                <button
                  type="button"
                  className={`filter-chip${evalCaseFilter === "all" ? " active" : ""}`}
                  onClick={() => onChangeEvalCaseFilter("all")}
                >
                  {copy.all}
                </button>
                <button
                  type="button"
                  className={`filter-chip${evalCaseFilter === "hit" ? " active" : ""}`}
                  onClick={() => onChangeEvalCaseFilter("hit")}
                >
                  {copy.hits}
                </button>
                <button
                  type="button"
                  className={`filter-chip${evalCaseFilter === "miss" ? " active" : ""}`}
                  onClick={() => onChangeEvalCaseFilter("miss")}
                >
                  {copy.misses}
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
                    <span>{item.matched ? copy.matched : copy.mismatch}</span>
                  </header>
                  <p>{item.question}</p>
                  <div className="meta-row">
                    <span>{copy.expected} {item.expected_route_type}</span>
                    <span>{copy.actual} {item.actual_route_type}</span>
                    {item.filename ? <span>{copy.file} {item.filename}</span> : null}
                  </div>
                  <small>{item.route_reason}</small>
                </article>
              ))}
            </div>
            {filteredAgentRouteCases.length === 0 && (
              <p className="muted">{copy.noCases}</p>
            )}
          </>
        ) : evaluationMode === "agent-workflow" && agentWorkflowEvalResult ? (
          <>
            <div className="summary-strip">
              <div className="summary-card">
                <span className="trace-label">{copy.totalCases}</span>
                <strong>{agentWorkflowEvalResult.report.summary.total_cases}</strong>
              </div>
              <div className="summary-card">
                <span className="trace-label">{copy.workflowAccuracy}</span>
                <strong>{agentWorkflowEvalResult.report.summary.workflow_accuracy.toFixed(3)}</strong>
              </div>
              <div className="summary-card">
                <span className="trace-label">{copy.matchedCases}</span>
                <strong>
                  {agentWorkflowEvalResult.report.cases.filter((item) => item.matched).length}
                </strong>
              </div>
            </div>
            <div className="panel-heading case-toolbar">
              <h3>{copy.caseResults}</h3>
              <div className="filter-row">
                <button
                  type="button"
                  className={`filter-chip${evalCaseFilter === "all" ? " active" : ""}`}
                  onClick={() => onChangeEvalCaseFilter("all")}
                >
                  {copy.all}
                </button>
                <button
                  type="button"
                  className={`filter-chip${evalCaseFilter === "hit" ? " active" : ""}`}
                  onClick={() => onChangeEvalCaseFilter("hit")}
                >
                  {copy.hits}
                </button>
                <button
                  type="button"
                  className={`filter-chip${evalCaseFilter === "miss" ? " active" : ""}`}
                  onClick={() => onChangeEvalCaseFilter("miss")}
                >
                  {copy.misses}
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
                    <span>{item.matched ? copy.matched : copy.mismatch}</span>
                  </header>
                  <p>{item.question}</p>
                  <div className="meta-row">
                    <span>
                      {copy.routeLabel} {item.expected_route_type} {"->"} {item.actual_route_type}
                    </span>
                    <span>
                      {copy.statusLabel} {item.expected_workflow_status} {"->"} {item.actual_workflow_status}
                    </span>
                    {item.filename ? <span>{copy.file} {item.filename}</span> : null}
                  </div>
                  <small>{item.route_reason}</small>
                </article>
              ))}
            </div>
            {filteredAgentWorkflowCases.length === 0 && (
              <p className="muted">{copy.noCases}</p>
            )}
          </>
        ) : (
          <div className="empty-state empty-state-large">
            <strong>{copy.noReport}</strong>
            <p>{copy.noReportCopy}</p>
          </div>
        )}
      </article>
    </section>
  );
}


