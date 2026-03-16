import type { FormEvent } from "react";

import type {
  AgentEvalDatasetInfo,
  AgentRouteEvalReportResponse,
  AgentWorkflowEvalReportResponse,
  EvalCaseFilter,
  EvalDatasetInfo,
  EvaluationReportHistoryEntry,
  EvaluationMetricsSummaryResponse,
  EvaluationOverviewResponse,
  EvaluationMode,
  EvalReportResponse,
  Locale,
  ToolExecutionEvalReportResponse,
} from "../types";

function hasFilenames(dataset: EvalDatasetInfo | AgentEvalDatasetInfo): dataset is EvalDatasetInfo {
  return "filenames" in dataset;
}

type EvaluationViewProps = {
  locale: Locale;
  evaluationMode: EvaluationMode;
  evaluationOverview: EvaluationOverviewResponse | null;
  evaluationMetricsSummary: EvaluationMetricsSummaryResponse | null;
  datasets: EvalDatasetInfo[];
  agentRouteDatasets: AgentEvalDatasetInfo[];
  agentWorkflowDatasets: AgentEvalDatasetInfo[];
  toolExecutionDatasets: AgentEvalDatasetInfo[];
  datasetName: string;
  evalTopK: number;
  evalResult: EvalReportResponse | null;
  agentRouteEvalResult: AgentRouteEvalReportResponse | null;
  agentWorkflowEvalResult: AgentWorkflowEvalReportResponse | null;
  toolExecutionEvalResult: ToolExecutionEvalReportResponse | null;
  evaluationHistory: EvaluationReportHistoryEntry[];
  evalError: string;
  evalBusy: boolean;
  evalCaseFilter: EvalCaseFilter;
  filteredEvalCases: EvalReportResponse["report"]["cases"];
  filteredAgentRouteCases: AgentRouteEvalReportResponse["report"]["cases"];
  filteredAgentWorkflowCases: AgentWorkflowEvalReportResponse["report"]["cases"];
  exportBusy: boolean;
  onRefreshDatasets: () => void;
  onExportBundle: () => void;
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
  evaluationMetricsSummary,
  datasets,
  agentRouteDatasets,
  agentWorkflowDatasets,
  toolExecutionDatasets,
  datasetName,
  evalTopK,
  evalResult,
  agentRouteEvalResult,
  agentWorkflowEvalResult,
  toolExecutionEvalResult,
  evaluationHistory,
  evalError,
  evalBusy,
  evalCaseFilter,
  filteredEvalCases,
  filteredAgentRouteCases,
  filteredAgentWorkflowCases,
  exportBusy,
  onRefreshDatasets,
  onExportBundle,
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
          metricsSummary: "评测亮点",
          metricsSummaryCopy: "汇总最值得关注的核心指标与代表性基准结果，用于快速判断当前系统质量。",
          summaryCacheStatus: "摘要缓存",
          benchmarkLabel: "代表性基准",
          benchmarkMetric: "主指标",
          exportBundle: "导出评估快照",
          exportingBundle: "导出中...",
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
          cacheStatus: "缓存状态",
          cached: "已缓存",
          fresh: "刚刚重算",
          unavailableMetric: "暂无数据",
          retrievalCopy: "运行预设检索基准并检查逐条 case 的排序结果。",
          routeCopy: "评估路由器是否选择了正确的工作流路径。",
          workflowCopy: "评估统一 agent workflow 是否落到预期状态。",
          toolExecutionCopy: "评估工具规划与执行是否返回正确的结构化结果。",
          retrievalTitle: "检索质量基准",
          routeTitle: "路由准确率基准",
          workflowTitle: "Agent Workflow 结果基准",
          toolExecutionTitle: "工具执行结果基准",
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
          toolAccuracy: "工具准确率",
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
          toolExecutionMode: "工具执行",
          cases: "条 case",
          actual: "实际",
          hitAt: "Hit@",
          noCases: "当前过滤条件下没有 case。",
          noReport: "暂无评测报告",
          noReportCopy: "选择数据集并运行评测后，可查看汇总指标和逐条 case 结果。",
          latestResult: "最近保存结果",
          reportSavedAt: "保存时间",
          reportSource: "结果来源",
          reportSourceSaved: "本地已保存",
          reportSourceFresh: "刚刚运行",
          reportHistory: "最近评测历史",
          previousDelta: "相较上次",
          improved: "提升",
          regressed: "下降",
          unchanged: "持平",
          metric: "指标",
        }
      : {
          workspace: "Evaluation Workspace",
          overview: "Evaluation Overview",
          metricsSummary: "Evaluation Highlights",
          metricsSummaryCopy:
            "Surface the key headline metrics and showcase benchmarks that best represent current system quality.",
          summaryCacheStatus: "Summary Cache",
          benchmarkLabel: "Showcase Benchmark",
          benchmarkMetric: "Primary Metric",
          exportBundle: "Export Evaluation Bundle",
          exportingBundle: "Exporting...",
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
          cacheStatus: "Cache Status",
          cached: "Cached",
          fresh: "Freshly Computed",
          unavailableMetric: "Unavailable",
          retrievalCopy: "Run curated retrieval benchmarks and inspect per-case ranking outcomes.",
          routeCopy: "Evaluate whether the router selects the correct workflow path.",
          workflowCopy: "Evaluate whether the unified agent workflow ends in the expected state.",
          toolExecutionCopy: "Evaluate whether tool planning and execution return the expected structured results.",
          retrievalTitle: "Benchmark Retrieval Quality",
          routeTitle: "Benchmark Routing Accuracy",
          workflowTitle: "Benchmark Agent Workflow Outcomes",
          toolExecutionTitle: "Benchmark Tool Execution Outcomes",
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
          toolAccuracy: "Tool Accuracy",
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
          toolExecutionMode: "Tool Execution",
          cases: "cases",
          actual: "actual",
          hitAt: "Hit@",
          noCases: "No cases match the current filter for this report.",
          noReport: "No evaluation report yet",
          noReportCopy:
            "Select a dataset and run evaluation to view benchmark summaries and per-case outcomes.",
          latestResult: "Latest Saved Result",
          reportSavedAt: "Saved At",
          reportSource: "Report Source",
          reportSourceSaved: "Saved",
          reportSourceFresh: "Fresh Run",
          reportHistory: "Recent Evaluation History",
          previousDelta: "Vs Previous",
          improved: "Improved",
          regressed: "Regressed",
          unchanged: "Unchanged",
          metric: "Metric",
        };
  const visibleDatasets =
    evaluationMode === "retrieval"
      ? datasets
      : evaluationMode === "agent-route"
        ? agentRouteDatasets
        : evaluationMode === "agent-workflow"
          ? agentWorkflowDatasets
          : toolExecutionDatasets;

  const activeReport =
    evaluationMode === "retrieval"
      ? evalResult
      : evaluationMode === "agent-route"
        ? agentRouteEvalResult
        : evaluationMode === "agent-workflow"
          ? agentWorkflowEvalResult
          : toolExecutionEvalResult;

  const modeCopy =
    evaluationMode === "retrieval"
      ? copy.retrievalCopy
      : evaluationMode === "agent-route"
        ? copy.routeCopy
        : evaluationMode === "agent-workflow"
          ? copy.workflowCopy
          : copy.toolExecutionCopy;
  const modeTitle =
    evaluationMode === "retrieval"
      ? copy.retrievalTitle
      : evaluationMode === "agent-route"
        ? copy.routeTitle
        : evaluationMode === "agent-workflow"
          ? copy.workflowTitle
          : copy.toolExecutionTitle;
  const overviewBestDataset = evaluationOverview?.retrieval.best_dataset_name
    ? `${evaluationOverview.retrieval.best_dataset_name} (${evaluationOverview.retrieval.best_hit_rate_at_k.toFixed(3)})`
    : copy.unavailableMetric;
  const overviewGeneratedAt = evaluationOverview?.generated_at
    ? new Date(evaluationOverview.generated_at).toLocaleString(locale === "zh" ? "zh-CN" : "en-US")
    : copy.unavailableMetric;
  const overviewCacheStatus = evaluationOverview
    ? evaluationOverview.cache_status === "cached"
      ? copy.cached
      : copy.fresh
    : copy.unavailableMetric;
  const metricsSummaryCacheStatus = evaluationMetricsSummary
    ? evaluationMetricsSummary.cache_status === "cached"
      ? copy.cached
      : copy.fresh
    : copy.unavailableMetric;
  const activeReportSavedAt = activeReport?.saved_at
    ? new Date(activeReport.saved_at).toLocaleString(locale === "zh" ? "zh-CN" : "en-US")
    : null;
  const activeReportSource = activeReport?.report_source
    ? activeReport.report_source === "saved"
      ? copy.reportSourceSaved
      : copy.reportSourceFresh
    : null;
  const previousHistoryEntry =
    evaluationHistory.length > 1 ? evaluationHistory[1] : null;
  const latestHistoryEntry = evaluationHistory.length > 0 ? evaluationHistory[0] : null;
  const historyDelta =
    latestHistoryEntry && previousHistoryEntry
      ? latestHistoryEntry.primary_metric_value - previousHistoryEntry.primary_metric_value
      : null;
  const historyDeltaLabel =
    historyDelta === null
      ? null
      : historyDelta > 0
        ? copy.improved
        : historyDelta < 0
          ? copy.regressed
          : copy.unchanged;

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
                  : evaluationMode === "agent-workflow"
                    ? copy.workflowMode
                    : copy.toolExecutionMode}
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
            <h2>{copy.metricsSummary}</h2>
            <p className="panel-intro">{copy.metricsSummaryCopy}</p>
          </div>
          <div className="button-cluster">
            <button type="button" className="ghost-button" onClick={onExportBundle} disabled={exportBusy}>
              {exportBusy ? copy.exportingBundle : copy.exportBundle}
            </button>
            <span className="status-pill">
              <span>{copy.summaryCacheStatus}</span>
              <strong>{metricsSummaryCacheStatus}</strong>
            </span>
          </div>
        </div>
        {evaluationMetricsSummary ? (
          <div className="overview-grid">
            <div className="summary-strip overview-summary-strip">
              {evaluationMetricsSummary.highlights.map((highlight) => (
                <div key={highlight.label} className="summary-card">
                  <span className="trace-label">{highlight.label}</span>
                  <strong>{highlight.value}</strong>
                  {highlight.detail ? <small>{highlight.detail}</small> : null}
                </div>
              ))}
            </div>
            <div className="highlights-benchmark-grid">
              {evaluationMetricsSummary.sections.map((section) => (
                <section key={`${section.title}-${section.dataset_name ?? "none"}`} className="subsection-card highlights-benchmark-card">
                  <div className="highlights-benchmark-header">
                    <div>
                      <span className="section-label">{copy.benchmarkLabel}</span>
                      <strong>{section.title}</strong>
                    </div>
                    <div className="highlights-benchmark-metric">
                      <span className="trace-label">{copy.benchmarkMetric}</span>
                      <strong>{section.formatted_value}</strong>
                    </div>
                  </div>
                  {section.dataset_name ? <p className="highlights-dataset-name">{section.dataset_name}</p> : null}
                  {section.detail ? <p className="panel-intro highlights-detail">{section.detail}</p> : null}
                </section>
              ))}
            </div>
          </div>
        ) : (
          <div className="empty-state">
            <strong>{copy.metricsSummary}</strong>
            <p>{copy.unavailableMetric}</p>
          </div>
        )}
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
                <span className="meta-pill muted-pill">
                  {copy.cacheStatus}: {overviewCacheStatus}
                </span>
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
            <button
              type="button"
              className={`filter-chip${evaluationMode === "tool-execution" ? " active" : ""}`}
              onClick={() => onChangeEvaluationMode("tool-execution")}
            >
              {copy.toolExecutionMode}
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
          {activeReportSavedAt || activeReportSource ? (
            <div className="pill-strip">
              <span className="meta-pill muted-pill">{copy.latestResult}</span>
              {activeReportSavedAt ? (
                <span className="meta-pill">
                  {copy.reportSavedAt}: {activeReportSavedAt}
                </span>
              ) : null}
              {activeReportSource ? (
                <span className="meta-pill">
                  {copy.reportSource}: {activeReportSource}
                </span>
              ) : null}
              {historyDelta !== null ? (
                <span className="meta-pill">
                  {copy.previousDelta}: {historyDeltaLabel} {historyDelta.toFixed(3)}
                </span>
              ) : null}
            </div>
          ) : null}
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
            {evaluationHistory.length > 0 && (
              <div className="subsection-card">
                <span className="section-label">{copy.reportHistory}</span>
                <div className="dataset-list">
                  {evaluationHistory.map((entry) => (
                    <article key={`${entry.saved_at}-${entry.primary_metric_name}`} className="dataset-card">
                      <strong>{new Date(entry.saved_at).toLocaleString(locale === "zh" ? "zh-CN" : "en-US")}</strong>
                      <div className="meta-row">
                        <span>{copy.metric} {entry.primary_metric_name}</span>
                        <span>{entry.primary_metric_value.toFixed(3)}</span>
                        <span>{copy.totalCases}: {entry.case_count}</span>
                      </div>
                    </article>
                  ))}
                </div>
              </div>
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
            {evaluationHistory.length > 0 && (
              <div className="subsection-card">
                <span className="section-label">{copy.reportHistory}</span>
                <div className="dataset-list">
                  {evaluationHistory.map((entry) => (
                    <article key={`${entry.saved_at}-${entry.primary_metric_name}`} className="dataset-card">
                      <strong>{new Date(entry.saved_at).toLocaleString(locale === "zh" ? "zh-CN" : "en-US")}</strong>
                      <div className="meta-row">
                        <span>{copy.metric} {entry.primary_metric_name}</span>
                        <span>{entry.primary_metric_value.toFixed(3)}</span>
                        <span>{copy.totalCases}: {entry.case_count}</span>
                      </div>
                    </article>
                  ))}
                </div>
              </div>
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
            {evaluationHistory.length > 0 && (
              <div className="subsection-card">
                <span className="section-label">{copy.reportHistory}</span>
                <div className="dataset-list">
                  {evaluationHistory.map((entry) => (
                    <article key={`${entry.saved_at}-${entry.primary_metric_name}`} className="dataset-card">
                      <strong>{new Date(entry.saved_at).toLocaleString(locale === "zh" ? "zh-CN" : "en-US")}</strong>
                      <div className="meta-row">
                        <span>{copy.metric} {entry.primary_metric_name}</span>
                        <span>{entry.primary_metric_value.toFixed(3)}</span>
                        <span>{copy.totalCases}: {entry.case_count}</span>
                      </div>
                    </article>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : evaluationMode === "tool-execution" && toolExecutionEvalResult ? (
          <>
            <div className="summary-strip">
              <div className="summary-card">
                <span className="trace-label">{copy.totalCases}</span>
                <strong>{toolExecutionEvalResult.report.summary.total_cases}</strong>
              </div>
              <div className="summary-card">
                <span className="trace-label">{copy.toolAccuracy}</span>
                <strong>{toolExecutionEvalResult.report.summary.tool_accuracy.toFixed(3)}</strong>
              </div>
              <div className="summary-card">
                <span className="trace-label">{copy.matchedCases}</span>
                <strong>
                  {toolExecutionEvalResult.report.cases.filter((item) => item.matched).length}
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
              {toolExecutionEvalResult.report.cases
                .filter((item) => {
                  if (evalCaseFilter === "hit") {
                    return item.matched;
                  }
                  if (evalCaseFilter === "miss") {
                    return !item.matched;
                  }
                  return true;
                })
                .map((item) => (
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
                      <span>{copy.expected} {item.expected_tool_name}:{item.expected_action}</span>
                      <span>{copy.actual} {item.actual_tool_name}:{item.actual_action}</span>
                    </div>
                    <small>
                      {copy.statusLabel} {item.expected_execution_status} {"->"} {item.actual_execution_status}
                    </small>
                  </article>
                ))}
            </div>
            {toolExecutionEvalResult.report.cases.filter((item) => {
              if (evalCaseFilter === "hit") {
                return item.matched;
              }
              if (evalCaseFilter === "miss") {
                return !item.matched;
              }
              return true;
            }).length === 0 && <p className="muted">{copy.noCases}</p>}
            {evaluationHistory.length > 0 && (
              <div className="subsection-card">
                <span className="section-label">{copy.reportHistory}</span>
                <div className="dataset-list">
                  {evaluationHistory.map((entry) => (
                    <article key={`${entry.saved_at}-${entry.primary_metric_name}`} className="dataset-card">
                      <strong>{new Date(entry.saved_at).toLocaleString(locale === "zh" ? "zh-CN" : "en-US")}</strong>
                      <div className="meta-row">
                        <span>{copy.metric} {entry.primary_metric_name}</span>
                        <span>{entry.primary_metric_value.toFixed(3)}</span>
                        <span>{copy.totalCases}: {entry.case_count}</span>
                      </div>
                    </article>
                  ))}
                </div>
              </div>
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


