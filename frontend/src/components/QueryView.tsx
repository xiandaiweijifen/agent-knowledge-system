import type { FormEvent } from "react";

import { useState } from "react";

import type {
  AgentWorkflowResponse,
  AgentWorkflowRunSummary,
  DiagnosticsResponse,
  DocumentItem,
  Locale,
  QueryResponse,
  ToolChainStep,
} from "../types";

type QueryViewProps = {
  locale?: Locale;
  documents: DocumentItem[];
  queryFilename: string;
  question: string;
  topK: number;
  activePresetQuestions: string[];
  queryResult: QueryResponse | null;
  agentQueryResult: AgentWorkflowResponse | null;
  agentWorkflowRuns: AgentWorkflowRunSummary[];
  diagnosticsResult: DiagnosticsResponse | null;
  queryError: string;
  queryBusy: boolean;
  onChangeDocument: (filename: string) => void;
  onChangeQuestion: (question: string) => void;
  onChangeTopK: (value: number) => void;
  onClearDiagnostics: () => void;
  onSubmitQuery: (event: FormEvent<HTMLFormElement>) => void;
  onRunAgent: () => void;
  onLoadAgentWorkflowRun: (runId: string) => void;
  onRecoverAgentWorkflowRun: (
    runId: string,
    recoveryAction?: string,
    clarificationContext?: Record<string, string>,
  ) => void;
  onRunDiagnostics: () => void;
};

export function QueryView({
  locale = "en",
  documents,
  queryFilename,
  question,
  topK,
  activePresetQuestions,
  queryResult,
  agentQueryResult,
  agentWorkflowRuns,
  diagnosticsResult,
  queryError,
  queryBusy,
  onChangeDocument,
  onChangeQuestion,
  onChangeTopK,
  onClearDiagnostics,
  onSubmitQuery,
  onRunAgent,
  onLoadAgentWorkflowRun,
  onRecoverAgentWorkflowRun,
  onRunDiagnostics,
}: QueryViewProps) {
  const [runSearch, setRunSearch] = useState("");
  const [runStatusFilter, setRunStatusFilter] = useState("all");
  const [runRecoveryFilter, setRunRecoveryFilter] = useState("all");
  const [focusedChainRootRunId, setFocusedChainRootRunId] = useState<string | null>(null);
  const [collapsedChainRootRunIds, setCollapsedChainRootRunIds] = useState<string[]>([]);
  const queryCopy =
    locale === "zh"
      ? {
          workspace: "查询工作台",
          bannerTitle: "回答追踪与检索检查",
          bannerCopy: "运行有依据的查询，比较回答链路，并检查向量分数与 rerank bonus 的行为。",
          noDocument: "未选择文档",
          answerReady: "回答已就绪",
          answerIdle: "回答未生成",
          diagnosticsReady: "诊断已就绪",
          diagnosticsIdle: "诊断未运行",
          queryLab: "查询实验台",
          queryLabCopy: "检查选中文档的检索行为、回答生成过程和 rerank 信号。",
          documentContext: "文档上下文",
          noDocumentContext: "无文档上下文（可选 Agent）",
          documentHint:
            "`运行 Query` 和 `运行 Diagnostics` 需要文档。`运行 Agent` 可在没有文档时执行工具或澄清工作流。",
          question: "问题",
          presetQuestions: "预设问题",
          topK: "Top-K",
          topKSummary: "top-k",
          noDocumentHint:
            "当前未选择文档上下文。仅检索类操作会被禁用，但 Agent 工具工作流仍可运行。",
          runningQuery: "正在运行查询工作流...",
          agentWorkflow: "Agent 工作流",
          workflowStatus: "工作流状态",
          route: "路由",
          answerProvider: "回答提供方",
          tool: "工具",
          routeReason: "路由原因",
          routeContext: "路由上下文",
          documentUsed: "文档",
          retrievalUsed: "检索",
          toolPlanningUsed: "工具规划",
          used: "已使用",
          notUsed: "未使用",
          workflowRecord: "工作流记录",
          recoveryChain: "恢复链",
          recoveryChainCopy: "查看当前工作流所属恢复链，并快速跳转到相关运行记录。",
          currentRun: "当前运行",
          rootRunBadge: "根运行",
          sourceRunBadge: "源运行",
          loadChainRun: "加载链上运行",
          previousChainRun: "上一链路运行",
          nextChainRun: "下一链路运行",
          runId: "Run Id",
          rootRun: "根 Run",
          loadRootRun: "加载根 Run",
          recoveryDepth: "恢复深度",
          resumedFrom: "恢复来源",
          sourceRun: "源 Run",
          loadSourceRun: "加载源 Run",
          recoveredVia: "恢复动作",
          resumeType: "恢复类型",
          resumedStep: "恢复步骤",
          notPersisted: "未持久化",
          notResumed: "未恢复",
          notLinked: "未关联",
          notResumedFromStep: "未从步骤恢复",
          reusedSteps: "复用步骤",
          none: "无",
          questionRewritten: "问题改写",
          yes: "是",
          no: "否",
          recoverySemantics: "恢复语义",
          outcome: "结果分类",
          retryState: "重试状态",
          recommended: "推荐动作",
          failureStage: "失败阶段",
          unknown: "未知",
          failurePrefix: "失败信息",
          knowledgeResult: "知识结果",
          executedSteps: "已执行步骤",
          executedStepsCopy: (count: number) => `这个工作流在返回最终结果前执行了 ${count} 个步骤。`,
          step: "步骤",
          target: "目标",
          planningMode: "规划模式",
          executionMode: "执行模式",
          finalStep: "最终步骤",
          toolPlan: "工具计划",
          action: "动作",
          finalStepCopy: "顶层快照展示的是最终执行步骤。完整链路请看上面的已执行步骤。",
          finalStepExecution: "最终步骤执行",
          toolExecution: "工具执行",
          clarificationPlan: "澄清计划",
          missing: "缺失",
          workflowTrace: "工作流轨迹",
          noWorkflow: "还没有 Agent 工作流",
          noWorkflowCopy: "运行 Agent 后可查看路由选择、工作流轨迹，以及工具或澄清输出。",
          recentRuns: "最近工作流运行",
          runSearch: "运行搜索",
          runSearchPlaceholder: "按问题或 run id 搜索",
          runStatusFilter: "状态筛选",
          runRecoveryFilter: "恢复筛选",
          chainScope: "链路聚焦",
          focusCurrentChain: "仅看当前链",
          clearChainFocus: "查看全部链路",
          chainScopeActive: "当前只显示同一恢复链上的运行记录。",
          chainRoot: "链根",
          chainRuns: "链内运行数",
          collapseChain: "折叠链路",
          expandChain: "展开链路",
          currentChain: "当前链",
          allRuns: "全部",
          noMatchingRuns: "没有匹配的工作流运行",
          noMatchingRunsCopy: "调整搜索词或筛选条件后再试。",
          routeMeta: "路由",
          runMeta: "运行",
          retryMeta: "重试",
          recommendedMeta: "推荐",
          recoveredViaMeta: "恢复动作",
          resumedFromMeta: "恢复自",
          reusedStepsMeta: "复用步骤",
          noHistory: "还没有工作流历史",
          noHistoryCopy: "运行 Agent 后会持久化工作流运行记录，并可在这里重新加载。",
          answerTrace: "回答链路",
          chatProvider: "对话提供方",
          chatModel: "对话模型",
          answerLatency: "回答耗时",
          embeddingProvider: "Embedding 提供方",
          queryProvider: "查询提供方",
          retrievalLatency: "检索耗时",
          topChunks: "Top 检索片段",
          chars: "字符",
          vector: "向量",
          bonus: "加成",
          noAnswerTrace: "还没有回答链路",
          noAnswerTraceCopy: "运行查询后可检查回答文本、模型提供方和 Top 检索片段。",
          retrievalDiagnostics: "检索诊断",
          scoredChunks: "评分片段数",
          candidates: "候选数",
          meanScore: "平均分",
          maxScore: "最高分",
          minScore: "最低分",
          latency: "耗时",
          candidateRanking: "候选排序",
          noDiagnostics: "还没有诊断结果",
          noDiagnosticsCopy: "运行诊断后可检查向量分数、rerank bonus 和候选排序。",
          supportingContext: "支撑上下文",
          searchQuery: "搜索问题",
          matchedDocuments: "匹配文档数",
          documents: "文档",
          searchSnippets: "搜索片段",
          executionStatus: "执行状态",
          mode: "模式",
          traceId: "Trace Id",
          notAvailable: "不可用",
          ticketId: "工单 Id",
          status: "状态",
          severity: "严重级别",
          environment: "环境",
          ticketCount: "工单数量",
          statusFilter: "状态筛选",
          noTicketsMatched: "当前筛选条件下没有工单。",
          toolOutput: "工具输出",
          noActions: "暂无可用恢复入口",
          recover: "恢复",
          recovering: "恢复中...",
          recoverRecommended: "按推荐动作恢复",
          loadRun: "加载运行记录",
          clarificationRequired: "该恢复动作需要先补充澄清字段，当前界面暂不支持直接执行。",
          clarificationInputs: "澄清字段",
          clarificationResume: "补充后恢复",
          clarificationResumeCopy: "填写缺失字段后，直接继续当前恢复动作。",
          clarificationFieldPlaceholder: "请输入",
          recoveryDetails: "恢复详情",
          recoveryAction: "恢复动作",
          clearDiagnostics: "清空诊断",
          runQuery: "运行 Query",
          runDiagnostics: "运行 Diagnostics",
          runAgent: "运行 Agent",
        }
      : {
          workspace: "Query Workspace",
          bannerTitle: "Answer Tracing And Retrieval Inspection",
          bannerCopy:
            "Run grounded queries, compare answer traces, and inspect vector score versus rerank bonus behavior.",
          noDocument: "no document",
          answerReady: "answer ready",
          answerIdle: "answer idle",
          diagnosticsReady: "diagnostics ready",
          diagnosticsIdle: "diagnostics idle",
          queryLab: "Query Lab",
          queryLabCopy:
            "Probe retrieval behavior, answer generation, and reranking signals for a selected document.",
          documentContext: "Document Context",
          noDocumentContext: "No document context (Agent optional)",
          documentHint:
            "`Run Query` and `Run Diagnostics` require a document. `Run Agent` can operate without one for tool execution or clarification workflows.",
          question: "Question",
          presetQuestions: "Preset Questions",
          topK: "Top-K",
          topKSummary: "top-k",
          noDocumentHint:
            "No document context selected. Retrieval-only actions are disabled, but agent tool workflows can still run.",
          runningQuery: "Running query workflow...",
          agentWorkflow: "Agent Workflow",
          workflowStatus: "Workflow Status",
          route: "Route",
          answerProvider: "Answer Provider",
          tool: "Tool",
          routeReason: "Route Reason",
          routeContext: "Route Context",
          documentUsed: "document",
          retrievalUsed: "retrieval",
          toolPlanningUsed: "tool planning",
          used: "used",
          notUsed: "not used",
          workflowRecord: "Workflow Record",
          recoveryChain: "Recovery Chain",
          recoveryChainCopy: "Inspect the current workflow lineage and jump directly to related runs.",
          currentRun: "Current Run",
          rootRunBadge: "Root Run",
          sourceRunBadge: "Source Run",
          loadChainRun: "Load Chain Run",
          previousChainRun: "Previous Chain Run",
          nextChainRun: "Next Chain Run",
          runId: "Run Id",
          rootRun: "Root Run",
          loadRootRun: "Load Root Run",
          recoveryDepth: "Recovery Depth",
          resumedFrom: "Resumed From",
          sourceRun: "Source Run",
          loadSourceRun: "Load Source Run",
          recoveredVia: "Recovered Via",
          resumeType: "Resume Type",
          resumedStep: "Resumed Step",
          notPersisted: "not persisted",
          notResumed: "not resumed",
          notLinked: "not linked",
          notResumedFromStep: "not resumed from step",
          reusedSteps: "reused steps",
          none: "none",
          questionRewritten: "question rewritten",
          yes: "yes",
          no: "no",
          recoverySemantics: "Recovery Semantics",
          outcome: "Outcome",
          retryState: "Retry State",
          recommended: "Recommended",
          failureStage: "Failure Stage",
          unknown: "unknown",
          failurePrefix: "Failure",
          knowledgeResult: "Knowledge Result",
          executedSteps: "Executed Steps",
          executedStepsCopy: (count: number) =>
            `The workflow executed ${count} step${count === 1 ? "" : "s"} before returning the final result.`,
          step: "Step",
          target: "Target",
          planningMode: "Planning Mode",
          executionMode: "Execution Mode",
          finalStep: "Final Step",
          toolPlan: "Tool Plan",
          action: "Action",
          finalStepCopy:
            "This top-level snapshot shows the final executed step. Use Executed Steps above to inspect the full chain.",
          finalStepExecution: "Final Step Execution",
          toolExecution: "Tool Execution",
          clarificationPlan: "Clarification Plan",
          missing: "missing",
          workflowTrace: "Workflow Trace",
          noWorkflow: "No agent workflow yet",
          noWorkflowCopy:
            "Run Agent to inspect route selection, workflow trace, and tool or clarification output.",
          recentRuns: "Recent Workflow Runs",
          runSearch: "Run Search",
          runSearchPlaceholder: "Search by question or run id",
          runStatusFilter: "Status Filter",
          runRecoveryFilter: "Recovery Filter",
          chainScope: "Chain Scope",
          focusCurrentChain: "Focus Current Chain",
          clearChainFocus: "Show All Chains",
          chainScopeActive: "Only runs from the current recovery chain are visible.",
          chainRoot: "Chain Root",
          chainRuns: "Chain Runs",
          collapseChain: "Collapse Chain",
          expandChain: "Expand Chain",
          currentChain: "Current Chain",
          allRuns: "All",
          noMatchingRuns: "No matching workflow runs",
          noMatchingRunsCopy: "Try a different search term or filter.",
          routeMeta: "route",
          runMeta: "run",
          retryMeta: "retry",
          recommendedMeta: "recommended",
          recoveredViaMeta: "recovered via",
          resumedFromMeta: "resumed from",
          reusedStepsMeta: "reused steps",
          noHistory: "No workflow history yet",
          noHistoryCopy:
            "Run Agent to persist workflow runs, then load a recent run from this panel.",
          answerTrace: "Answer Trace",
          chatProvider: "Chat Provider",
          chatModel: "Chat Model",
          answerLatency: "Answer Latency",
          embeddingProvider: "Embedding Provider",
          queryProvider: "Query Provider",
          retrievalLatency: "Retrieval Latency",
          topChunks: "Top Retrieved Chunks",
          chars: "chars",
          vector: "vector",
          bonus: "bonus",
          noAnswerTrace: "No answer trace yet",
          noAnswerTraceCopy:
            "Run a query to inspect answer text, provider selection, and top retrieved chunks.",
          retrievalDiagnostics: "Retrieval Diagnostics",
          scoredChunks: "Scored Chunks",
          candidates: "Candidates",
          meanScore: "Mean Score",
          maxScore: "Max Score",
          minScore: "Min Score",
          latency: "Latency",
          candidateRanking: "Candidate Ranking",
          noDiagnostics: "No diagnostics yet",
          noDiagnosticsCopy:
            "Run diagnostics to inspect vector scores, rerank bonuses, and candidate ordering.",
          supportingContext: "Supporting Context",
          searchQuery: "Search Query",
          matchedDocuments: "Matched Documents",
          documents: "Documents",
          searchSnippets: "Search Snippets",
          executionStatus: "Execution Status",
          mode: "Mode",
          traceId: "Trace Id",
          notAvailable: "n/a",
          ticketId: "Ticket Id",
          status: "Status",
          severity: "Severity",
          environment: "Environment",
          ticketCount: "Ticket Count",
          statusFilter: "Status Filter",
          noTicketsMatched: "No tickets matched the current filter.",
          toolOutput: "Tool Output",
          noActions: "No recovery actions available",
          recover: "Recover",
          recovering: "Recovering...",
          recoverRecommended: "Recover With Recommendation",
          loadRun: "Load Run",
          clarificationRequired:
            "This recovery action requires clarification fields and cannot be executed directly from the current UI.",
          clarificationInputs: "Clarification Fields",
          clarificationResume: "Recover With Clarification",
          clarificationResumeCopy:
            "Provide the missing fields and continue the recovery action directly from the UI.",
          clarificationFieldPlaceholder: "Enter",
          recoveryDetails: "Recovery Details",
          recoveryAction: "Recovery Action",
          clearDiagnostics: "Clear Diagnostics",
          runQuery: "Run Query",
          runDiagnostics: "Run Diagnostics",
          runAgent: "Run Agent",
        };

  function formatRecoveryActionLabel(action: string) {
    switch (action) {
      case "resume_from_failed_step":
        return locale === "zh" ? "从失败步骤继续" : "Resume From Failed Step";
      case "manual_retrigger":
        return locale === "zh" ? "人工重新触发" : "Manual Retrigger";
      case "resume_with_clarification":
        return locale === "zh" ? "补充澄清后继续" : "Resume With Clarification";
      case "retry":
        return locale === "zh" ? "重试" : "Retry";
      case "manual_investigation":
        return locale === "zh" ? "人工排查" : "Manual Investigation";
      case "none":
        return locale === "zh" ? "无需恢复" : "No Recovery Needed";
      default:
        return action;
    }
  }

  function formatResumeStrategyLabel(strategy: string) {
    switch (strategy) {
      case "search_then_ticket_failed_step_resume":
        return locale === "zh" ? "搜索后工单失败步骤恢复" : "Search Then Ticket Failed-Step Resume";
      case "status_then_ticket_failed_step_resume":
        return locale === "zh" ? "状态后工单失败步骤恢复" : "Status Then Ticket Failed-Step Resume";
      case "search_then_summarize_failed_step_resume":
        return locale === "zh" ? "搜索后总结失败步骤恢复" : "Search Then Summarize Failed-Step Resume";
      case "status_then_summarize_failed_step_resume":
        return locale === "zh" ? "状态后总结失败步骤恢复" : "Status Then Summarize Failed-Step Resume";
      case "manual_retrigger_recovery":
        return locale === "zh" ? "人工重触发恢复" : "Manual Retrigger Recovery";
      case "retry_recovery":
        return locale === "zh" ? "重试恢复" : "Retry Recovery";
      default:
        return strategy;
    }
  }

  function formatClarificationFieldLabel(field: string) {
    const labels =
      locale === "zh"
        ? {
            search_query_refinement: "搜索词细化",
            execution_confirmation: "执行确认",
            document_scope: "文档范围",
            environment: "环境",
            fallback_action: "回退动作",
            task_details: "任务详情",
            target: "目标",
            action: "动作",
            priority: "优先级",
            filename: "文件名",
          }
        : {
            search_query_refinement: "Search Query Refinement",
            execution_confirmation: "Execution Confirmation",
            document_scope: "Document Scope",
            environment: "Environment",
            fallback_action: "Fallback Action",
            task_details: "Task Details",
            target: "Target",
            action: "Action",
            priority: "Priority",
            filename: "Filename",
          };
    if (field in labels) {
      return labels[field as keyof typeof labels];
    }

    return field
      .split("_")
      .filter(Boolean)
      .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
      .join(" ");
  }

  function getClarificationFields(
    recoveryActionDetails: AgentWorkflowResponse["recovery_action_details"] | undefined,
    clarificationPlan?: AgentWorkflowResponse["clarification_plan"],
  ) {
    const detailFields = recoveryActionDetails?.resume_with_clarification?.missing_fields;
    if (Array.isArray(detailFields)) {
      return detailFields.filter((item): item is string => typeof item === "string" && item.length > 0);
    }

    if (clarificationPlan?.missing_fields) {
      return clarificationPlan.missing_fields;
    }

    return [];
  }

  function renderRecoveryActions(actions: string[] | undefined, mutedWhenEmpty = false) {
    if (!actions || actions.length === 0) {
      return (
        <span className={`meta-pill${mutedWhenEmpty ? " muted-pill" : ""}`}>
          {queryCopy.noActions}
        </span>
      );
    }

    return actions.map((action) => (
      <span key={action} className="meta-pill">
        {formatRecoveryActionLabel(action)} ({action})
      </span>
    ));
  }

  function isRecoveryActionExecutable(action: string) {
    return action !== "resume_with_clarification" && action !== "manual_investigation";
  }

  function formatRecoveryDetailValue(value: unknown) {
    if (Array.isArray(value)) {
      return value.join(", ");
    }
    if (typeof value === "boolean") {
      return value ? queryCopy.yes : queryCopy.no;
    }
    if (value === null || value === undefined || value === "") {
      return queryCopy.none;
    }
    return String(value);
  }

  function submitClarificationRecovery(
    event: FormEvent<HTMLFormElement>,
    runId: string,
  ) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const clarificationContext = Object.fromEntries(
      Array.from(form.entries())
        .filter(([, value]) => typeof value === "string" && value.trim().length > 0)
        .map(([key, value]) => [key, String(value).trim()]),
    );
    onRecoverAgentWorkflowRun(runId, "resume_with_clarification", clarificationContext);
  }

  function renderClarificationRecoveryForm(
    runId: string | null | undefined,
    recoveryActionDetails: AgentWorkflowResponse["recovery_action_details"] | undefined,
    clarificationPlan?: AgentWorkflowResponse["clarification_plan"],
  ) {
    if (!runId) {
      return null;
    }

    const missingFields = getClarificationFields(recoveryActionDetails, clarificationPlan);
    if (missingFields.length === 0) {
      return <p className="subsection-copy">{queryCopy.clarificationRequired}</p>;
    }

    return (
      <form className="clarification-recovery-form" onSubmit={(event) => submitClarificationRecovery(event, runId)}>
        <span className="trace-label">{queryCopy.clarificationInputs}</span>
        <p className="subsection-copy">{queryCopy.clarificationResumeCopy}</p>
        <div className="clarification-field-grid">
          {missingFields.map((field) => (
            <label key={field} className="clarification-field">
              <span>{formatClarificationFieldLabel(field)}</span>
              <input
                type="text"
                name={field}
                placeholder={`${queryCopy.clarificationFieldPlaceholder} ${formatClarificationFieldLabel(field)}`}
                disabled={queryBusy}
              />
            </label>
          ))}
        </div>
        <div className="button-row">
          <button type="submit" className="primary-button" disabled={queryBusy}>
            {queryBusy
              ? queryCopy.recovering
              : `${queryCopy.clarificationResume}: ${formatRecoveryActionLabel("resume_with_clarification")}`}
          </button>
        </div>
      </form>
    );
  }

  function renderRecoveryButtons(
    runId: string | null | undefined,
    actions: string[] | undefined,
    recommendedAction: string | null | undefined,
    recoveryActionDetails?: AgentWorkflowResponse["recovery_action_details"],
    clarificationPlan?: AgentWorkflowResponse["clarification_plan"],
  ) {
    if (!runId || !actions || actions.length === 0) {
      return null;
    }

    const executableActions = actions.filter(isRecoveryActionExecutable);
    const needsClarification = actions.includes("resume_with_clarification");

    return (
      <>
        {executableActions.length > 0 && (
          <div className="button-row">
            {executableActions.map((action) => (
              <button
                key={action}
                type="button"
                className={action === recommendedAction ? "primary-button" : "ghost-button"}
                disabled={queryBusy}
                aria-label={`${queryCopy.recover} ${runId} ${formatRecoveryActionLabel(action)}`}
                onClick={() => onRecoverAgentWorkflowRun(runId, action)}
              >
                {queryBusy && action === recommendedAction
                  ? queryCopy.recovering
                  : `${queryCopy.recover}: ${formatRecoveryActionLabel(action)}`}
              </button>
            ))}
          </div>
        )}
        {needsClarification &&
          renderClarificationRecoveryForm(runId, recoveryActionDetails, clarificationPlan)}
      </>
    );
  }

  function renderRecoveryActionDetails(
    recoveryActionDetails: AgentWorkflowResponse["recovery_action_details"] | undefined,
  ) {
    if (!recoveryActionDetails || Object.keys(recoveryActionDetails).length === 0) {
      return null;
    }

    return (
      <article className="subsection-card">
        <span className="section-label">{queryCopy.recoveryDetails}</span>
        <div className="tool-output-grid">
          {Object.entries(recoveryActionDetails).map(([action, details]) => (
            <div key={action} className="tool-output-card">
              <span className="trace-label">
                {queryCopy.recoveryAction}: {formatRecoveryActionLabel(action)}
              </span>
              {Object.entries(details).map(([key, value]) => (
                <strong key={key}>
                  {key}: {formatRecoveryDetailValue(value)}
                </strong>
              ))}
            </div>
          ))}
        </div>
      </article>
    );
  }

  function getWorkflowRunRouteType(run: AgentWorkflowResponse | AgentWorkflowRunSummary) {
    if ("route" in run && run.route) {
      return run.route.route_type;
    }
    if ("route_type" in run && run.route_type) {
      return run.route_type;
    }
    return queryCopy.unknown;
  }

  function renderSupportingContext(
    output: Record<string, string>,
  ) {
    const supportingQuery = output.supporting_query;
    const supportingDocuments = output.supporting_documents;
    const supportingSnippets = output.supporting_snippets;
    const supportingMatchCount = output.supporting_match_count;

    if (
      !supportingQuery &&
      !supportingDocuments &&
      !supportingSnippets &&
      !supportingMatchCount
    ) {
      return null;
    }

    return (
      <article className="supporting-context-card">
        <span className="section-label">{queryCopy.supportingContext}</span>
        <div className="trace-grid">
          {supportingQuery && (
            <div>
              <span className="trace-label">{queryCopy.searchQuery}</span>
              <strong>{supportingQuery}</strong>
            </div>
          )}
          {supportingMatchCount && (
            <div>
              <span className="trace-label">{queryCopy.matchedDocuments}</span>
              <strong>{supportingMatchCount}</strong>
            </div>
          )}
        </div>
        {supportingDocuments && (
          <div className="supporting-block">
            <span className="trace-label">{queryCopy.documents}</span>
            <p className="long-text-block">{supportingDocuments}</p>
          </div>
        )}
        {supportingSnippets && (
          <div className="supporting-block">
            <span className="trace-label">{queryCopy.searchSnippets}</span>
            <p className="long-text-block">{supportingSnippets}</p>
          </div>
        )}
      </article>
    );
  }

  function renderToolExecutionDetails(
    toolExecution: AgentWorkflowResponse["tool_execution"] | ToolChainStep["tool_execution"],
  ) {
    if (!toolExecution) {
      return null;
    }

    const listItems =
      toolExecution.tool_name === "ticketing" && toolExecution.action === "list"
        ? (toolExecution.output.tickets || "")
            .split(" | ")
            .map((item) => item.trim())
            .filter(Boolean)
        : [];

    return (
      <>
        <div className="trace-grid">
          <div>
            <span className="trace-label">{queryCopy.executionStatus}</span>
            <strong>{toolExecution.execution_status}</strong>
          </div>
          <div>
            <span className="trace-label">{queryCopy.mode}</span>
            <strong>{toolExecution.execution_mode}</strong>
          </div>
          <div>
            <span className="trace-label">{queryCopy.traceId}</span>
            <strong className="trace-code">{toolExecution.trace_id}</strong>
          </div>
        </div>
        <p className="subsection-copy">{toolExecution.result_summary}</p>
        {toolExecution.tool_name === "ticketing" && toolExecution.action !== "list" && (
          <div className="ticketing-highlight">
            <div className="trace-grid">
              <div>
                <span className="trace-label">{queryCopy.ticketId}</span>
                <strong className="trace-code">{toolExecution.output.ticket_id ?? queryCopy.notAvailable}</strong>
              </div>
              <div>
                <span className="trace-label">{queryCopy.status}</span>
                <strong>{toolExecution.output.status ?? queryCopy.notAvailable}</strong>
              </div>
              <div>
                <span className="trace-label">{queryCopy.severity}</span>
                <strong>{toolExecution.output.severity ?? queryCopy.notAvailable}</strong>
              </div>
              <div>
                <span className="trace-label">{queryCopy.environment}</span>
                <strong>{toolExecution.output.environment ?? queryCopy.notAvailable}</strong>
              </div>
            </div>
          </div>
        )}
        {toolExecution.tool_name === "ticketing" && renderSupportingContext(toolExecution.output)}
        {toolExecution.tool_name === "ticketing" && toolExecution.action === "list" && (
          <div className="ticketing-highlight">
            <div className="trace-grid">
              <div>
                <span className="trace-label">{queryCopy.ticketCount}</span>
                <strong>{toolExecution.output.ticket_count ?? "0"}</strong>
              </div>
              <div>
                <span className="trace-label">{queryCopy.statusFilter}</span>
                <strong>{toolExecution.output.status_filter ?? "all"}</strong>
              </div>
            </div>
            {listItems.length > 0 ? (
              <div className="list-block">
                {listItems.map((item) => (
                  <p key={item}>{item}</p>
                ))}
              </div>
            ) : (
              <p className="subsection-copy">{queryCopy.noTicketsMatched}</p>
            )}
          </div>
        )}
        {Object.keys(toolExecution.output).length > 0 &&
          !(toolExecution.tool_name === "ticketing" && toolExecution.action === "list") && (
            <>
              <span className="section-label">{queryCopy.toolOutput}</span>
              <div className="tool-output-grid">
                {Object.entries(toolExecution.output)
                  .filter(
                    ([key]) =>
                      ![
                        "supporting_query",
                        "supporting_documents",
                        "supporting_snippets",
                        "supporting_match_count",
                      ].includes(key),
                  )
                  .map(([key, value]) => (
                  <article key={key} className="tool-output-card">
                    <span className="trace-label">{key}</span>
                    <strong>{value}</strong>
                  </article>
                  ))}
              </div>
            </>
          )}
      </>
    );
  }

  const hasDocument = documents.length > 0 && Boolean(queryFilename);
  const hasQuestion = question.trim().length > 0;
  const routeUsesFilename =
    agentQueryResult?.route.route_type === "knowledge_retrieval" && !!agentQueryResult.filename;
  const routeUsesRetrieval = !!agentQueryResult?.retrieval;
  const routeUsesToolPlanning = !!agentQueryResult?.tool_plan;
  const hasToolChain = (agentQueryResult?.tool_chain.length ?? 0) > 0;
  const currentRunId = agentQueryResult?.run_id ?? null;
  const currentRootRunId = agentQueryResult?.root_run_id ?? agentQueryResult?.run_id ?? null;
  const normalizedRunSearch = runSearch.trim().toLowerCase();
  const relatedWorkflowRuns = agentQueryResult
    ? [
        agentQueryResult,
        ...agentWorkflowRuns.filter((run) => {
          const runRootId = run.root_run_id ?? run.run_id ?? null;
          return Boolean(currentRootRunId) && runRootId === currentRootRunId;
        }),
      ]
        .filter(
          (run, index, items) =>
            Boolean(run.run_id) &&
            items.findIndex((candidate) => candidate.run_id === run.run_id) === index,
        )
        .sort((left, right) => {
          const depthDelta = (left.recovery_depth ?? 0) - (right.recovery_depth ?? 0);
          if (depthDelta !== 0) {
            return depthDelta;
          }

          const leftTime = left.started_at ?? left.last_updated_at ?? "";
          const rightTime = right.started_at ?? right.last_updated_at ?? "";
          return leftTime.localeCompare(rightTime);
        })
    : [];
  const currentChainIndex = relatedWorkflowRuns.findIndex((run) => run.run_id === currentRunId);
  const previousChainRun =
    currentChainIndex > 0 ? relatedWorkflowRuns[currentChainIndex - 1] : null;
  const nextChainRun =
    currentChainIndex >= 0 && currentChainIndex < relatedWorkflowRuns.length - 1
      ? relatedWorkflowRuns[currentChainIndex + 1]
      : null;
  const filteredWorkflowRuns = agentWorkflowRuns.filter((run) => {
    if (focusedChainRootRunId) {
      const runRootId = run.root_run_id ?? run.run_id ?? null;
      if (runRootId !== focusedChainRootRunId) {
        return false;
      }
    }

    if (runStatusFilter !== "all" && run.workflow_status !== runStatusFilter) {
      return false;
    }

    if (
      runRecoveryFilter !== "all" &&
      (run.recommended_recovery_action ?? "none") !== runRecoveryFilter
    ) {
      return false;
    }

    if (!normalizedRunSearch) {
      return true;
    }

    return [run.question, run.run_id, run.root_run_id, run.source_run_id]
      .filter((value): value is string => typeof value === "string" && value.length > 0)
      .some((value) => value.toLowerCase().includes(normalizedRunSearch));
  });
  const groupedFilteredWorkflowRuns = filteredWorkflowRuns.reduce<
    Array<{ rootRunId: string; runs: AgentWorkflowRunSummary[] }>
  >((groups, run) => {
    const rootRunId = run.root_run_id ?? run.run_id;
    const existingGroup = groups.find((group) => group.rootRunId === rootRunId);
    if (existingGroup) {
      existingGroup.runs.push(run);
      return groups;
    }
    groups.push({ rootRunId, runs: [run] });
    return groups;
  }, []);

  function isChainCollapsed(rootRunId: string) {
    return collapsedChainRootRunIds.includes(rootRunId);
  }

  function toggleChainCollapsed(rootRunId: string) {
    setCollapsedChainRootRunIds((current) =>
      current.includes(rootRunId)
        ? current.filter((id) => id !== rootRunId)
        : [...current, rootRunId],
    );
  }

  return (
    <section className="panel-grid query-layout">
      <article className="panel panel-span view-banner">
        <div className="view-banner-content">
          <div>
            <span className="section-label">{queryCopy.workspace}</span>
            <h2 className="view-banner-title">{queryCopy.bannerTitle}</h2>
            <p className="view-banner-copy">{queryCopy.bannerCopy}</p>
          </div>
          <div className="view-banner-meta">
            <span>{queryFilename || queryCopy.noDocument}</span>
            <span>{queryCopy.topKSummary} {topK}</span>
            <span>{queryResult ? queryCopy.answerReady : queryCopy.answerIdle}</span>
            <span>{diagnosticsResult ? queryCopy.diagnosticsReady : queryCopy.diagnosticsIdle}</span>
          </div>
        </div>
      </article>

      <article className="panel">
        <div className="panel-heading">
          <div>
            <h2>{queryCopy.queryLab}</h2>
            <p className="panel-intro">{queryCopy.queryLabCopy}</p>
          </div>
          <button type="button" className="ghost-button" onClick={onClearDiagnostics}>
            {queryCopy.clearDiagnostics}
          </button>
        </div>
        <form className="stack-form" onSubmit={onSubmitQuery}>
          <label>
            {queryCopy.documentContext}
            <select
              value={queryFilename}
              onChange={(event) => onChangeDocument(event.target.value)}
              disabled={documents.length === 0}
            >
              <option value="">{queryCopy.noDocumentContext}</option>
              {documents.map((item) => (
                <option key={item.filename} value={item.filename}>
                  {item.filename}
                </option>
              ))}
            </select>
          </label>
          <p className="muted">
            {queryCopy.documentHint}
          </p>
          <label>
            {queryCopy.question}
            <textarea value={question} onChange={(event) => onChangeQuestion(event.target.value)} rows={4} />
          </label>
          <div className="preset-block">
            <span className="section-label">{queryCopy.presetQuestions}</span>
            <div className="preset-strip">
              {activePresetQuestions.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  className="preset-chip"
                  onClick={() => onChangeQuestion(preset)}
                >
                  {preset}
                </button>
              ))}
            </div>
          </div>
          <label>
            {queryCopy.topK}
            <input
              type="number"
              min={1}
              max={10}
              value={topK}
              onChange={(event) => onChangeTopK(Number(event.target.value))}
            />
          </label>
          <div className="button-row">
            <button type="submit" className="primary-button" disabled={queryBusy || !hasDocument || !hasQuestion}>
              {queryCopy.runQuery}
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={queryBusy || !hasDocument || !hasQuestion}
              onClick={onRunDiagnostics}
            >
              {queryCopy.runDiagnostics}
            </button>
            <button
              type="button"
              className="ghost-button"
              disabled={queryBusy || !hasQuestion}
              onClick={onRunAgent}
            >
              {queryCopy.runAgent}
            </button>
          </div>
        </form>
        {!hasDocument && (
          <p className="muted">
            {queryCopy.noDocumentHint}
          </p>
        )}
        {queryBusy && <p className="status">{queryCopy.runningQuery}</p>}
        {queryError && <p className="error">{queryError}</p>}
      </article>

      <div className="query-results">
        <article className="panel">
          <div className="panel-heading">
            <h2>{queryCopy.agentWorkflow}</h2>
          </div>
          {agentQueryResult ? (
            <div className="result-stack">
              <div className="trace-grid">
                <div>
                    <span className="trace-label">{queryCopy.workflowStatus}</span>
                  <strong>{agentQueryResult.workflow_status}</strong>
                </div>
                <div>
                    <span className="trace-label">{queryCopy.route}</span>
                  <strong>{agentQueryResult.route.route_type}</strong>
                </div>
                <div>
                    <span className="trace-label">{queryCopy.answerProvider}</span>
                    <strong>{agentQueryResult.chat_provider ?? queryCopy.notUsed}</strong>
                </div>
                <div>
                    <span className="trace-label">{queryCopy.tool}</span>
                    <strong>{agentQueryResult.tool_plan?.tool_name ?? queryCopy.notUsed}</strong>
                </div>
              </div>

              <article className="subsection-card">
                <span className="section-label">{queryCopy.routeReason}</span>
                <p className="subsection-copy">{agentQueryResult.route.route_reason}</p>
              </article>

              <article className="subsection-card">
                <span className="section-label">{queryCopy.routeContext}</span>
                <div className="pill-strip">
                  <span className={`meta-pill${routeUsesFilename ? "" : " muted-pill"}`}>
                    {queryCopy.documentUsed} {routeUsesFilename ? `${queryCopy.used}: ${agentQueryResult.filename}` : queryCopy.notUsed}
                  </span>
                  <span className={`meta-pill${routeUsesRetrieval ? "" : " muted-pill"}`}>
                    {queryCopy.retrievalUsed} {routeUsesRetrieval ? queryCopy.used : queryCopy.notUsed}
                  </span>
                  <span className={`meta-pill${routeUsesToolPlanning ? "" : " muted-pill"}`}>
                    {queryCopy.toolPlanningUsed} {routeUsesToolPlanning ? queryCopy.used : queryCopy.notUsed}
                  </span>
                </div>
              </article>

              <article className="subsection-card">
                <span className="section-label">{queryCopy.workflowRecord}</span>
                <div className="trace-grid workflow-record-grid">
                  <div>
                    <span className="trace-label">{queryCopy.runId}</span>
                    <strong className="trace-code">{agentQueryResult.run_id ?? queryCopy.notPersisted}</strong>
                  </div>
                  <div>
                    <span className="trace-label">{queryCopy.rootRun}</span>
                    <strong className="trace-code">{agentQueryResult.root_run_id ?? queryCopy.notLinked}</strong>
                    {agentQueryResult.root_run_id && agentQueryResult.root_run_id !== agentQueryResult.run_id && (
                      <button
                        type="button"
                        className="inline-link-button"
                        onClick={() => onLoadAgentWorkflowRun(agentQueryResult.root_run_id!)}
                      >
                        {queryCopy.loadRootRun}
                      </button>
                    )}
                  </div>
                  <div>
                    <span className="trace-label">{queryCopy.recoveryDepth}</span>
                    <strong>{agentQueryResult.recovery_depth ?? 0}</strong>
                  </div>
                  <div>
                    <span className="trace-label">{queryCopy.resumedFrom}</span>
                    <strong>{agentQueryResult.resumed_from_question ?? queryCopy.notResumed}</strong>
                  </div>
                  <div>
                    <span className="trace-label">{queryCopy.sourceRun}</span>
                    <strong className="trace-code">{agentQueryResult.source_run_id ?? queryCopy.notLinked}</strong>
                    {agentQueryResult.source_run_id && (
                      <button
                        type="button"
                        className="inline-link-button"
                        onClick={() => onLoadAgentWorkflowRun(agentQueryResult.source_run_id!)}
                      >
                        {queryCopy.loadSourceRun}
                      </button>
                    )}
                  </div>
                  <div>
                    <span className="trace-label">{queryCopy.recoveredVia}</span>
                    <strong>
                      {agentQueryResult.recovered_via_action
                        ? formatRecoveryActionLabel(agentQueryResult.recovered_via_action)
                        : queryCopy.notResumed}
                    </strong>
                  </div>
                  <div>
                    <span className="trace-label">{queryCopy.resumeType}</span>
                    <strong>{agentQueryResult.resume_strategy ? formatResumeStrategyLabel(agentQueryResult.resume_strategy) : queryCopy.notResumed}</strong>
                    {agentQueryResult.resume_strategy && (
                      <small className="trace-code trace-code-subtle">{agentQueryResult.resume_strategy}</small>
                    )}
                  </div>
                  <div>
                    <span className="trace-label">{queryCopy.resumedStep}</span>
                    <strong>
                      {agentQueryResult.resumed_from_step_index ?? queryCopy.notResumedFromStep}
                    </strong>
                  </div>
                </div>
                <div className="pill-strip">
                  <span
                    className={`meta-pill${
                      (agentQueryResult.reused_step_indices?.length ?? 0) > 0 ? "" : " muted-pill"
                    }`}
                  >
                    {queryCopy.reusedSteps}{" "}
                    {(agentQueryResult.reused_step_indices?.length ?? 0) > 0
                      ? agentQueryResult.reused_step_indices?.join(", ")
                      : queryCopy.none}
                  </span>
                  <span className="meta-pill">
                    {queryCopy.questionRewritten} {agentQueryResult.question_rewritten ? queryCopy.yes : queryCopy.no}
                  </span>
                </div>
              </article>

              {relatedWorkflowRuns.length > 0 && (
                <article className="subsection-card">
                  <span className="section-label">{queryCopy.recoveryChain}</span>
                  <p className="subsection-copy">{queryCopy.recoveryChainCopy}</p>
                  {(previousChainRun || nextChainRun) && (
                    <div className="button-row">
                      {previousChainRun?.run_id && (
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={queryBusy}
                          onClick={() => onLoadAgentWorkflowRun(previousChainRun.run_id!)}
                        >
                          {queryCopy.previousChainRun}
                        </button>
                      )}
                      {nextChainRun?.run_id && (
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={queryBusy}
                          onClick={() => onLoadAgentWorkflowRun(nextChainRun.run_id!)}
                        >
                          {queryCopy.nextChainRun}
                        </button>
                      )}
                    </div>
                  )}
                  <div className="recovery-chain-list">
                    {relatedWorkflowRuns.map((run) => {
                      const runId = run.run_id ?? queryCopy.notPersisted;
                      const isCurrentRun = run.run_id === currentRunId;
                      const isRootRun =
                        Boolean(currentRootRunId) && run.run_id === currentRootRunId;
                      const isSourceRun =
                        Boolean(agentQueryResult.source_run_id) &&
                        run.run_id === agentQueryResult.source_run_id;

                      return (
                        <article
                          key={runId}
                          className={`recovery-chain-card${isCurrentRun ? " is-current" : ""}`}
                        >
                          <div className="card-title-row">
                            <strong>{run.question}</strong>
                            <span className="status-chip">{run.workflow_status}</span>
                          </div>
                          <div className="meta-row">
                            <span>{queryCopy.runMeta} {runId}</span>
                            <span>{queryCopy.recoveryDepth}: {run.recovery_depth ?? 0}</span>
                          </div>
                          <div className="meta-row">
                            <span>{queryCopy.routeMeta} {getWorkflowRunRouteType(run)}</span>
                            <span>
                              {queryCopy.recoveredViaMeta}:{" "}
                              {run.recovered_via_action
                                ? formatRecoveryActionLabel(run.recovered_via_action)
                                : queryCopy.none}
                            </span>
                          </div>
                          <div className="pill-strip">
                            {isCurrentRun && <span className="meta-pill">{queryCopy.currentRun}</span>}
                            {isRootRun && <span className="meta-pill">{queryCopy.rootRunBadge}</span>}
                            {isSourceRun && <span className="meta-pill">{queryCopy.sourceRunBadge}</span>}
                            {run.resume_strategy && (
                              <span className="meta-pill">
                                {formatResumeStrategyLabel(run.resume_strategy)}
                              </span>
                            )}
                          </div>
                          {!isCurrentRun && run.run_id && (
                            <div className="button-row">
                              <button
                                type="button"
                                className="ghost-button"
                                disabled={queryBusy}
                                onClick={() => onLoadAgentWorkflowRun(run.run_id!)}
                              >
                                {queryCopy.loadChainRun}
                              </button>
                            </div>
                          )}
                        </article>
                      );
                    })}
                  </div>
                </article>
              )}

              <article className="subsection-card">
                <span className="section-label">{queryCopy.recoverySemantics}</span>
                <div className="trace-grid">
                  <div>
                    <span className="trace-label">{queryCopy.outcome}</span>
                    <strong>{agentQueryResult.outcome_category ?? queryCopy.unknown}</strong>
                  </div>
                  <div>
                    <span className="trace-label">{queryCopy.retryState}</span>
                    <strong>{agentQueryResult.retry_state ?? queryCopy.unknown}</strong>
                  </div>
                  <div>
                    <span className="trace-label">{queryCopy.recommended}</span>
                    <strong>
                      {formatRecoveryActionLabel(
                        agentQueryResult.recommended_recovery_action ?? "none",
                      )}
                    </strong>
                  </div>
                  <div>
                    <span className="trace-label">{queryCopy.failureStage}</span>
                    <strong>{agentQueryResult.failure_stage ?? queryCopy.notAvailable}</strong>
                  </div>
                </div>
                <div className="pill-strip">
                  {renderRecoveryActions(agentQueryResult.available_recovery_actions, true)}
                </div>
                {renderRecoveryButtons(
                  agentQueryResult.run_id,
                  agentQueryResult.available_recovery_actions,
                  agentQueryResult.recommended_recovery_action,
                  agentQueryResult.recovery_action_details,
                  agentQueryResult.clarification_plan,
                )}
                {agentQueryResult.failure_message && (
                  <p className="subsection-copy">
                    <strong>{queryCopy.failurePrefix}:</strong> {agentQueryResult.failure_message}
                  </p>
                )}
              </article>

              {renderRecoveryActionDetails(agentQueryResult.recovery_action_details)}

              {agentQueryResult.answer && (
                <article className="subsection-card">
                  <span className="section-label">{queryCopy.knowledgeResult}</span>
                  <blockquote className="answer-card">{agentQueryResult.answer}</blockquote>
                </article>
              )}

              {hasToolChain && (
                <article className="subsection-card">
                  <span className="section-label">{queryCopy.executedSteps}</span>
                  <p className="subsection-copy">{queryCopy.executedStepsCopy(agentQueryResult.tool_chain.length)}</p>
                  <div className="tool-chain-list">
                    {agentQueryResult.tool_chain.map((step, index) => (
                      <article
                        key={`${step.question}-${index + 1}`}
                        className="tool-chain-card"
                      >
                        <header className="tool-chain-header">
                          <div>
                            <span className="section-label">
                              {queryCopy.step} {step.step_index}
                            </span>
                            <h3>{step.tool_plan.tool_name}</h3>
                          </div>
                          <span className="status-chip success">
                            {step.tool_plan.action}
                          </span>
                        </header>
                        <p className="subsection-copy">
                          <strong>{queryCopy.question}:</strong> {step.question}
                        </p>
                        <div className="trace-grid">
                          <div>
                            <span className="trace-label">{queryCopy.target}</span>
                            <strong>{step.tool_plan.target}</strong>
                          </div>
                          <div>
                            <span className="trace-label">{queryCopy.planningMode}</span>
                            <strong>{step.tool_plan.planning_mode}</strong>
                          </div>
                          <div>
                            <span className="trace-label">{queryCopy.executionMode}</span>
                            <strong>{step.tool_execution?.execution_mode ?? queryCopy.notUsed}</strong>
                          </div>
                        </div>
                        {Object.keys(step.tool_plan.arguments).length > 0 && (
                          <div className="pill-strip">
                            {Object.entries(step.tool_plan.arguments).map(([key, value]) => (
                              <span key={key} className="meta-pill">
                                {key}: {value}
                              </span>
                            ))}
                          </div>
                        )}
                        {renderToolExecutionDetails(step.tool_execution)}
                      </article>
                    ))}
                  </div>
                </article>
              )}

              {agentQueryResult.tool_plan && (
                <article className="subsection-card">
                  <span className="section-label">
                    {hasToolChain ? queryCopy.finalStep : queryCopy.toolPlan}
                  </span>
                  <div className="trace-grid">
                    <div>
                      <span className="trace-label">{queryCopy.tool}</span>
                      <strong>{agentQueryResult.tool_plan.tool_name}</strong>
                    </div>
                    <div>
                      <span className="trace-label">{queryCopy.action}</span>
                      <strong>{agentQueryResult.tool_plan.action}</strong>
                    </div>
                    <div>
                      <span className="trace-label">{queryCopy.target}</span>
                      <strong>{agentQueryResult.tool_plan.target}</strong>
                    </div>
                    <div>
                      <span className="trace-label">{queryCopy.planningMode}</span>
                      <strong>{agentQueryResult.tool_plan.planning_mode}</strong>
                    </div>
                  </div>
                  {Object.keys(agentQueryResult.tool_plan.arguments).length > 0 && (
                    <div className="pill-strip">
                      {Object.entries(agentQueryResult.tool_plan.arguments).map(([key, value]) => (
                        <span key={key} className="meta-pill">
                          {key}: {value}
                        </span>
                      ))}
                    </div>
                  )}
                  <p className="subsection-copy">{agentQueryResult.tool_plan.plan_summary}</p>
                  {hasToolChain && (
                    <p className="muted">{queryCopy.finalStepCopy}</p>
                  )}
                </article>
              )}

              {agentQueryResult.tool_execution && (
                <article className="subsection-card">
                  <span className="section-label">
                    {hasToolChain ? queryCopy.finalStepExecution : queryCopy.toolExecution}
                  </span>
                  {renderToolExecutionDetails(agentQueryResult.tool_execution)}
                </article>
              )}

              {agentQueryResult.clarification_plan && (
                <article className="subsection-card">
                  <span className="section-label">{queryCopy.clarificationPlan}</span>
                  <p className="subsection-copy">
                    {agentQueryResult.clarification_message ??
                      agentQueryResult.clarification_plan.clarification_summary}
                  </p>
                  {agentQueryResult.clarification_plan.missing_fields.length > 0 && (
                    <div className="pill-strip">
                      {agentQueryResult.clarification_plan.missing_fields.map((field) => (
                        <span key={field} className="meta-pill">
                          {queryCopy.missing}: {field}
                        </span>
                      ))}
                    </div>
                  )}
                  {agentQueryResult.clarification_plan.follow_up_questions.length > 0 && (
                    <div className="list-block">
                      {agentQueryResult.clarification_plan.follow_up_questions.map((item) => (
                        <p key={item}>{item}</p>
                      ))}
                    </div>
                  )}
                </article>
              )}

              <div className="section-label">{queryCopy.workflowTrace}</div>
              <div className="trace-event-list">
                {agentQueryResult.workflow_trace.map((event) => (
                  <article key={`${event.stage}-${event.timestamp}`} className="trace-event-card">
                    <header>
                      <strong>{event.stage}</strong>
                      <span>{event.status}</span>
                    </header>
                    <p>{event.detail}</p>
                    <small>{event.timestamp}</small>
                  </article>
                ))}
              </div>
            </div>
          ) : (
            <div className="empty-state empty-state-large">
              <strong>{queryCopy.noWorkflow}</strong>
              <p>{queryCopy.noWorkflowCopy}</p>
            </div>
          )}
        </article>

        <article className="panel">
          <div className="panel-heading">
            <h2>{queryCopy.recentRuns}</h2>
          </div>
          {agentWorkflowRuns.length > 0 ? (
            <>
              <div className="run-filter-grid">
                <label>
                  {queryCopy.runSearch}
                  <input
                    type="text"
                    value={runSearch}
                    placeholder={queryCopy.runSearchPlaceholder}
                    onChange={(event) => setRunSearch(event.target.value)}
                  />
                </label>
                <label>
                  {queryCopy.runStatusFilter}
                  <select
                    value={runStatusFilter}
                    onChange={(event) => setRunStatusFilter(event.target.value)}
                  >
                    <option value="all">{queryCopy.allRuns}</option>
                    <option value="completed">completed</option>
                    <option value="failed">failed</option>
                    <option value="clarification_required">clarification_required</option>
                  </select>
                </label>
                <label>
                  {queryCopy.runRecoveryFilter}
                  <select
                    value={runRecoveryFilter}
                    onChange={(event) => setRunRecoveryFilter(event.target.value)}
                  >
                    <option value="all">{queryCopy.allRuns}</option>
                    <option value="none">none</option>
                    <option value="resume_from_failed_step">resume_from_failed_step</option>
                    <option value="resume_with_clarification">resume_with_clarification</option>
                    <option value="manual_retrigger">manual_retrigger</option>
                    <option value="retry">retry</option>
                  </select>
                </label>
                <label>
                  {queryCopy.chainScope}
                  <div className="filter-toggle-row">
                    <button
                      type="button"
                      className="ghost-button"
                      disabled={queryBusy || !currentRootRunId}
                      onClick={() => setFocusedChainRootRunId(currentRootRunId)}
                    >
                      {queryCopy.focusCurrentChain}
                    </button>
                    <button
                      type="button"
                      className="ghost-button"
                      disabled={queryBusy || !focusedChainRootRunId}
                      onClick={() => setFocusedChainRootRunId(null)}
                    >
                      {queryCopy.clearChainFocus}
                    </button>
                  </div>
                </label>
              </div>
              {focusedChainRootRunId && (
                <p className="subsection-copy">{queryCopy.chainScopeActive}</p>
              )}
              {groupedFilteredWorkflowRuns.length > 0 ? (
            <div className="run-list">
              {groupedFilteredWorkflowRuns.map((group) => {
                const isCurrentChain = Boolean(currentRootRunId) && group.rootRunId === currentRootRunId;
                const isCollapsed = isChainCollapsed(group.rootRunId);
                const completedCount = group.runs.filter((run) => run.workflow_status === "completed").length;
                const failedCount = group.runs.filter((run) => run.workflow_status === "failed").length;
                const clarificationCount = group.runs.filter(
                  (run) => run.workflow_status === "clarification_required",
                ).length;

                return (
                  <article key={group.rootRunId} className="run-chain-group">
                    <div className="card-title-row">
                      <strong>{queryCopy.chainRoot}: {group.rootRunId}</strong>
                      <div className="button-row">
                        {isCurrentChain && <span className="meta-pill">{queryCopy.currentChain}</span>}
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={queryBusy}
                          onClick={() => toggleChainCollapsed(group.rootRunId)}
                        >
                          {isCollapsed ? queryCopy.expandChain : queryCopy.collapseChain}
                        </button>
                      </div>
                    </div>
                    <div className="meta-row">
                      <span>{queryCopy.chainRuns}: {group.runs.length}</span>
                      <span>
                        completed {completedCount} | failed {failedCount} | clarification_required {clarificationCount}
                      </span>
                    </div>
                    {!isCollapsed && (
                      <div className="run-chain-runs">
                        {group.runs.map((run) => (
                          <article key={run.run_id} className="run-card">
                            <div className="card-title-row">
                              <strong>{run.question}</strong>
                              <span className="status-chip">{run.workflow_status}</span>
                            </div>
                            <div className="meta-row">
                              <span>{queryCopy.routeMeta} {run.route_type}</span>
                              <span>{queryCopy.runMeta} {run.run_id}</span>
                            </div>
                            <div className="meta-row">
                              <span>{queryCopy.rootRun}: {run.root_run_id ?? queryCopy.notLinked}</span>
                              <span>{queryCopy.recoveryDepth}: {run.recovery_depth ?? 0}</span>
                            </div>
                            <div className="meta-row">
                              <span>{queryCopy.retryMeta} {run.retry_state ?? queryCopy.unknown}</span>
                              <span>{queryCopy.recommendedMeta} {run.recommended_recovery_action ?? queryCopy.none}</span>
                            </div>
                            {run.recovered_via_action && (
                              <p className="subsection-copy">
                                {queryCopy.recoveredViaMeta}: {formatRecoveryActionLabel(run.recovered_via_action)}
                              </p>
                            )}
                            <div className="pill-strip">
                              {renderRecoveryActions(run.available_recovery_actions, true)}
                            </div>
                            {run.resumed_from_question && (
                              <p className="subsection-copy">{queryCopy.resumedFromMeta}: {run.resumed_from_question}</p>
                            )}
                            {(run.reused_step_indices?.length ?? 0) > 0 && (
                              <p className="subsection-copy">
                                {queryCopy.reusedStepsMeta}: {run.reused_step_indices?.join(", ")}
                              </p>
                            )}
                            <div className="button-row">
                              <button
                                type="button"
                                className="ghost-button"
                                disabled={queryBusy}
                                onClick={() => onLoadAgentWorkflowRun(run.run_id)}
                              >
                                {queryCopy.loadRun}
                              </button>
                            </div>
                            {renderRecoveryButtons(
                              run.run_id,
                              run.available_recovery_actions,
                              run.recommended_recovery_action,
                              run.recovery_action_details,
                            )}
                          </article>
                        ))}
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
              ) : (
                <div className="empty-state">
                  <strong>{queryCopy.noMatchingRuns}</strong>
                  <p>{queryCopy.noMatchingRunsCopy}</p>
                </div>
              )}
            </>
          ) : (
            <div className="empty-state">
              <strong>{queryCopy.noHistory}</strong>
              <p>{queryCopy.noHistoryCopy}</p>
            </div>
          )}
        </article>

        <article className="panel">
          <div className="panel-heading">
            <h2>{queryCopy.answerTrace}</h2>
          </div>
          {queryResult ? (
            <div className="result-stack">
              <div className="trace-grid">
                <div>
                  <span className="trace-label">{queryCopy.chatProvider}</span>
                  <strong>{queryResult.chat_provider}</strong>
                </div>
                <div>
                  <span className="trace-label">{queryCopy.chatModel}</span>
                  <strong>{queryResult.chat_model}</strong>
                </div>
                <div>
                  <span className="trace-label">{queryCopy.answerLatency}</span>
                  <strong>{queryResult.answer_latency_ms.toFixed(3)} ms</strong>
                </div>
                <div>
                  <span className="trace-label">{queryCopy.embeddingProvider}</span>
                  <strong>{queryResult.retrieval.embedding_provider}</strong>
                </div>
                <div>
                  <span className="trace-label">{queryCopy.queryProvider}</span>
                  <strong>{queryResult.retrieval.query_embedding_provider}</strong>
                </div>
                <div>
                  <span className="trace-label">{queryCopy.retrievalLatency}</span>
                  <strong>{queryResult.retrieval.retrieval_latency_ms.toFixed(3)} ms</strong>
                </div>
              </div>
              <blockquote className="answer-card">{queryResult.answer}</blockquote>
              <div className="section-label">{queryCopy.topChunks}</div>
              <div className="match-list compact">
                {queryResult.retrieval.matches.map((match) => (
                  <article key={match.chunk_id} className="match-card trace-card">
                    <header>
                      <strong>{match.chunk_id}</strong>
                      <span>{match.score.toFixed(6)}</span>
                    </header>
                    <div className="meta-row">
                      <span>{queryCopy.chars} {match.char_count}</span>
                      <span>{queryCopy.vector} {match.vector_score?.toFixed(6) ?? "-"}</span>
                      <span>{queryCopy.bonus} {match.rerank_bonus?.toFixed(6) ?? "-"}</span>
                    </div>
                    <p>{match.content}</p>
                  </article>
                ))}
              </div>
            </div>
          ) : (
            <div className="empty-state empty-state-large">
              <strong>{queryCopy.noAnswerTrace}</strong>
              <p>{queryCopy.noAnswerTraceCopy}</p>
            </div>
          )}
        </article>

        <article className="panel">
          <div className="panel-heading">
            <h2>{queryCopy.retrievalDiagnostics}</h2>
          </div>
          {diagnosticsResult ? (
            <>
              <div className="trace-grid">
                <div>
                  <span className="trace-label">{queryCopy.scoredChunks}</span>
                  <strong>{diagnosticsResult.diagnostics.total_scored_chunks}</strong>
                </div>
                <div>
                  <span className="trace-label">{queryCopy.candidates}</span>
                  <strong>{diagnosticsResult.diagnostics.returned_candidate_count}</strong>
                </div>
                <div>
                  <span className="trace-label">{queryCopy.meanScore}</span>
                  <strong>{diagnosticsResult.diagnostics.mean_score.toFixed(6)}</strong>
                </div>
                <div>
                  <span className="trace-label">{queryCopy.maxScore}</span>
                  <strong>{diagnosticsResult.diagnostics.max_score.toFixed(6)}</strong>
                </div>
                <div>
                  <span className="trace-label">{queryCopy.minScore}</span>
                  <strong>{diagnosticsResult.diagnostics.min_score.toFixed(6)}</strong>
                </div>
                <div>
                  <span className="trace-label">{queryCopy.latency}</span>
                  <strong>{diagnosticsResult.retrieval.retrieval_latency_ms.toFixed(3)} ms</strong>
                </div>
              </div>
              <div className="section-label">{queryCopy.candidateRanking}</div>
              <div className="match-list compact">
                {diagnosticsResult.candidates.map((match) => (
                  <article key={match.chunk_id} className="match-card diagnostic trace-card">
                    <header>
                      <strong>{match.chunk_id}</strong>
                      <span>{match.score.toFixed(6)}</span>
                    </header>
                    <div className="meta-row">
                      <span>{queryCopy.vector} {match.vector_score?.toFixed(6) ?? "-"}</span>
                      <span>{queryCopy.bonus} {match.rerank_bonus?.toFixed(6) ?? "-"}</span>
                      <span>{queryCopy.chars} {match.char_count}</span>
                    </div>
                    <p>{match.content}</p>
                  </article>
                ))}
              </div>
            </>
          ) : (
            <div className="empty-state empty-state-large">
              <strong>{queryCopy.noDiagnostics}</strong>
              <p>{queryCopy.noDiagnosticsCopy}</p>
            </div>
          )}
        </article>
      </div>
    </section>
  );
}
