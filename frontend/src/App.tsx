import { FormEvent, useEffect, useState } from "react";
import {
  deleteDocument as deleteDocumentRequest,
  fetchAgentRouteEvaluationDatasets,
  fetchAgentRouteEvaluationHistory,
  fetchAgentWorkflowEvaluationDatasets,
  fetchAgentWorkflowEvaluationHistory,
  fetchAgentWorkflowRun,
  fetchAgentWorkflowRuns,
  fetchDocumentPreview,
  fetchDocuments,
  fetchEvaluationDatasets,
  fetchEvaluationExportBundle,
  fetchEvaluationMetricsSummary,
  fetchEvaluationHistory,
  fetchEvaluationOverview,
  fetchLatestAgentRouteEvaluation,
  fetchLatestAgentWorkflowEvaluation,
  fetchLatestEvaluation,
  fetchLatestToolExecutionEvaluation,
  fetchPersistedChunks,
  fetchPersistedEmbeddings,
  fetchSystemHealth,
  fetchToolExecutionEvaluationDatasets,
  fetchToolExecutionEvaluationHistory,
  persistChunks as persistChunksRequest,
  persistEmbeddings as persistEmbeddingsRequest,
  recoverAgentWorkflowRun as recoverAgentWorkflowRunRequest,
  runAgentRouteEvaluation as runAgentRouteEvaluationRequest,
  runAgentWorkflowEvaluation as runAgentWorkflowEvaluationRequest,
  runToolExecutionEvaluation as runToolExecutionEvaluationRequest,
  runAgentQuery as runAgentQueryRequest,
  runDiagnostics as runDiagnosticsRequest,
  runEvaluation as runEvaluationRequest,
  runQuery as runQueryRequest,
  uploadDocument as uploadDocumentRequest,
} from "./api";
import { DocumentsView } from "./components/DocumentsView";
import { EvaluationView } from "./components/EvaluationView";
import { QueryView } from "./components/QueryView";
import { getViews, presetQuestions } from "./constants";
import type {
  AgentWorkflowResponse,
  AgentWorkflowRunSummary,
  AgentEvalDatasetInfo,
  AgentRouteEvalReportResponse,
  AgentWorkflowEvalReportResponse,
  DiagnosticsResponse,
  DocumentItem,
  DocumentPreview,
  EvalCaseFilter,
  EvalDatasetInfo,
  EvaluationReportHistoryEntry,
  EvaluationOverviewResponse,
  EvaluationMode,
  EvaluationMetricsSummaryResponse,
  EvalReportResponse,
  ToolExecutionEvalReportResponse,
  PersistedChunkDocument,
  PersistedEmbeddingDocument,
  QueryResponse,
  SystemHealthResponse,
  Locale,
  ViewKey,
} from "./types";

function App() {
  const [activeView, setActiveView] = useState<ViewKey>("documents");
  const [locale, setLocale] = useState<Locale>("en");

  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedFilename, setSelectedFilename] = useState("");
  const [preview, setPreview] = useState<DocumentPreview | null>(null);
  const [chunkArtifact, setChunkArtifact] = useState<PersistedChunkDocument | null>(null);
  const [embeddingArtifact, setEmbeddingArtifact] = useState<PersistedEmbeddingDocument | null>(null);
  const [documentsError, setDocumentsError] = useState("");
  const [documentsBusy, setDocumentsBusy] = useState(false);
  const [artifactBusy, setArtifactBusy] = useState(false);
  const [artifactMessage, setArtifactMessage] = useState("");
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");
  const [systemHealth, setSystemHealth] = useState<SystemHealthResponse | null>(null);
  const [systemHealthError, setSystemHealthError] = useState("");

  const [queryFilename, setQueryFilename] = useState("");
  const [question, setQuestion] = useState("What is RAG?");
  const [topK, setTopK] = useState(3);
  const [queryResult, setQueryResult] = useState<QueryResponse | null>(null);
  const [agentQueryResult, setAgentQueryResult] = useState<AgentWorkflowResponse | null>(null);
  const [agentWorkflowRuns, setAgentWorkflowRuns] = useState<AgentWorkflowRunSummary[]>([]);
  const [diagnosticsResult, setDiagnosticsResult] = useState<DiagnosticsResponse | null>(null);
  const [queryError, setQueryError] = useState("");
  const [queryBusy, setQueryBusy] = useState(false);

  const [datasets, setDatasets] = useState<EvalDatasetInfo[]>([]);
  const [agentRouteDatasets, setAgentRouteDatasets] = useState<AgentEvalDatasetInfo[]>([]);
  const [agentWorkflowDatasets, setAgentWorkflowDatasets] = useState<AgentEvalDatasetInfo[]>([]);
  const [toolExecutionDatasets, setToolExecutionDatasets] = useState<AgentEvalDatasetInfo[]>([]);
  const [evaluationMode, setEvaluationMode] = useState<EvaluationMode>("retrieval");
  const [datasetName, setDatasetName] = useState("");
  const [evalTopK, setEvalTopK] = useState(3);
  const [evalResult, setEvalResult] = useState<EvalReportResponse | null>(null);
  const [agentRouteEvalResult, setAgentRouteEvalResult] = useState<AgentRouteEvalReportResponse | null>(null);
  const [agentWorkflowEvalResult, setAgentWorkflowEvalResult] =
    useState<AgentWorkflowEvalReportResponse | null>(null);
  const [toolExecutionEvalResult, setToolExecutionEvalResult] =
    useState<ToolExecutionEvalReportResponse | null>(null);
  const [evaluationOverview, setEvaluationOverview] = useState<EvaluationOverviewResponse | null>(null);
  const [evaluationMetricsSummary, setEvaluationMetricsSummary] =
    useState<EvaluationMetricsSummaryResponse | null>(null);
  const [evaluationHistory, setEvaluationHistory] = useState<EvaluationReportHistoryEntry[]>([]);
  const [evalError, setEvalError] = useState("");
  const [evalBusy, setEvalBusy] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [evalCaseFilter, setEvalCaseFilter] = useState<EvalCaseFilter>("all");
  const [latestEvalRevision, setLatestEvalRevision] = useState(0);

  const activePresetQuestions =
    presetQuestions[queryFilename] ?? [
      "What is the main topic of this document?",
      "What are the most important system behaviors described here?",
    ];
  const views = getViews(locale);
  const appCopy = {
    en: {
      eyebrow: "Enterprise RAG Agent Console",
      heroCopy:
        "A focused console for inspecting ingestion artifacts, tracing retrieval, and benchmarking retrieval quality across curated datasets.",
      documents: "Documents",
      evalDatasets: "Eval Datasets",
      defaultTopK: "Default Query Top-K",
      brand: "Agent Knowledge System",
      systemSnapshot: "System Snapshot",
      systemSnapshotCopy:
        "Active providers and infrastructure readiness for the current backend session.",
      backend: "Backend",
      environment: "Environment",
      embedding: "Embedding",
      chat: "Chat",
      providerKeys: "Provider Keys",
      infra: "Infra",
      unavailable: "unavailable",
      unknown: "unknown",
      on: "on",
      off: "off",
      modules: "Console Modules",
      modulesCopy:
        "Choose the operating surface for ingestion, retrieval diagnostics, or benchmark review.",
      language: "Language",
      english: "English",
      chinese: "中文",
    },
    zh: {
      eyebrow: "企业级 RAG Agent 控制台",
      heroCopy: "一个聚焦于摄取产物检查、检索追踪和基准评测的控制台。",
      documents: "文档数",
      evalDatasets: "评测数据集",
      defaultTopK: "默认查询 Top-K",
      brand: "Agent Knowledge System",
      systemSnapshot: "系统快照",
      systemSnapshotCopy: "展示当前后端会话中的活跃提供方与基础设施就绪状态。",
      backend: "后端",
      environment: "环境",
      embedding: "嵌入模型",
      chat: "对话模型",
      providerKeys: "提供方密钥",
      infra: "基础设施",
      unavailable: "不可用",
      unknown: "未知",
      on: "开启",
      off: "关闭",
      modules: "控制台模块",
      modulesCopy: "选择用于摄取、检索诊断或基准结果查看的工作界面。",
      language: "语言",
      english: "English",
      chinese: "中文",
    },
  }[locale];

  const filteredEvalCases =
    evalResult?.report.cases.filter((item) => {
      if (evalCaseFilter === "hit") {
        return item.hit_at_k;
      }

      if (evalCaseFilter === "miss") {
        return !item.hit_at_k;
      }

      return true;
    }) ?? [];

  const filteredAgentRouteCases =
    agentRouteEvalResult?.report.cases.filter((item) => {
      if (evalCaseFilter === "hit") {
        return item.matched;
      }
      if (evalCaseFilter === "miss") {
        return !item.matched;
      }
      return true;
    }) ?? [];

  const filteredAgentWorkflowCases =
    agentWorkflowEvalResult?.report.cases.filter((item) => {
      if (evalCaseFilter === "hit") {
        return item.matched;
      }
      if (evalCaseFilter === "miss") {
        return !item.matched;
      }
      return true;
    }) ?? [];

  const visibleDatasetOptions =
    evaluationMode === "retrieval"
      ? datasets
      : evaluationMode === "agent-route"
        ? agentRouteDatasets
        : evaluationMode === "agent-workflow"
          ? agentWorkflowDatasets
          : toolExecutionDatasets;

  useEffect(() => {
    void loadSystemHealth();
    void loadDocuments();
    void loadEvaluationDatasets();
    void loadAgentWorkflowRuns();
  }, []);

  useEffect(() => {
    if (!selectedFilename && documents.length > 0) {
      setSelectedFilename(documents[0].filename);
    }
  }, [documents, selectedFilename]);

  useEffect(() => {
    if (!selectedFilename) {
      return;
    }

    void loadPreview(selectedFilename);
    void loadArtifactStatus(selectedFilename);
  }, [selectedFilename]);

  function resetQueryOutputs() {
    setQueryResult(null);
    setAgentQueryResult(null);
    setDiagnosticsResult(null);
    setQueryError("");
  }

  async function loadAgentWorkflowRuns() {
    try {
      const payload = await fetchAgentWorkflowRuns(8);
      setAgentWorkflowRuns(payload.runs);
    } catch {
      setAgentWorkflowRuns([]);
    }
  }

  function handleSelectDocument(filename: string) {
    setSelectedFilename(filename);
    resetQueryOutputs();
  }

  function handleChangeQueryDocument(filename: string) {
    setQueryFilename(filename);
    resetQueryOutputs();
  }

  async function loadDocuments() {
    setDocumentsBusy(true);
    setDocumentsError("");

    try {
      const payload = await fetchDocuments();
      setDocuments(payload.documents);

      if (payload.documents.length > 0) {
        setSelectedFilename((current) => current || payload.documents[0].filename);
      }
    } catch (error) {
      setDocumentsError(error instanceof Error ? error.message : "Failed to load documents");
    } finally {
      setDocumentsBusy(false);
    }
  }

  async function deleteDocument() {
    if (!selectedFilename) {
      return;
    }

    const confirmed = window.confirm(
      `Delete ${selectedFilename} and its persisted chunk / embedding artifacts?`,
    );

    if (!confirmed) {
      return;
    }

    setArtifactBusy(true);
    setArtifactMessage("");
    setUploadMessage("");
    setDocumentsError("");

    try {
      await deleteDocumentRequest(selectedFilename);
      setArtifactMessage(`Deleted ${selectedFilename} and related artifacts.`);
      setPreview(null);
      setChunkArtifact(null);
      setEmbeddingArtifact(null);
      resetQueryOutputs();

      const payload = await fetchDocuments();
      setDocuments(payload.documents);

      if (payload.documents.length > 0) {
        setSelectedFilename(payload.documents[0].filename);
      } else {
        setSelectedFilename("");
        setQueryFilename("");
      }
    } catch (error) {
      setDocumentsError(error instanceof Error ? error.message : "Failed to delete document");
    } finally {
      setArtifactBusy(false);
    }
  }

  async function loadSystemHealth() {
    setSystemHealthError("");

    try {
      const payload = await fetchSystemHealth();
      setSystemHealth(payload);
    } catch (error) {
      setSystemHealth(null);
      setSystemHealthError(error instanceof Error ? error.message : "Failed to load system status");
    }
  }

  async function uploadDocument(file: File) {
    setUploadBusy(true);
    setUploadMessage("");
    setDocumentsError("");

    try {
      const payload = await uploadDocumentRequest(file);
      setUploadMessage(`Uploaded ${payload.filename} successfully.`);
      await loadDocuments();
      setSelectedFilename(payload.filename);
    } catch (error) {
      setDocumentsError(error instanceof Error ? error.message : "Failed to upload document");
    } finally {
      setUploadBusy(false);
    }
  }

  async function loadPreview(filename: string) {
    setDocumentsBusy(true);
    setDocumentsError("");

    try {
      const payload = await fetchDocumentPreview(filename);
      setPreview(payload);
    } catch (error) {
      setPreview(null);
      setDocumentsError(error instanceof Error ? error.message : "Failed to load preview");
    } finally {
      setDocumentsBusy(false);
    }
  }

  async function loadArtifactStatus(filename: string) {
    setArtifactBusy(true);
    setArtifactMessage("");

    try {
      const [chunkResult, embeddingResult] = await Promise.allSettled([
        fetchPersistedChunks(filename),
        fetchPersistedEmbeddings(filename),
      ]);

      setChunkArtifact(chunkResult.status === "fulfilled" ? chunkResult.value : null);
      setEmbeddingArtifact(embeddingResult.status === "fulfilled" ? embeddingResult.value : null);
    } finally {
      setArtifactBusy(false);
    }
  }

  async function persistChunks() {
    if (!selectedFilename) {
      return;
    }

    setArtifactBusy(true);
    setArtifactMessage("");
    setDocumentsError("");

    try {
      const payload = await persistChunksRequest(selectedFilename);
      setChunkArtifact(payload);
      setArtifactMessage("Persisted paragraph chunks successfully.");
      setEmbeddingArtifact(null);
    } catch (error) {
      setDocumentsError(error instanceof Error ? error.message : "Failed to persist chunks");
    } finally {
      setArtifactBusy(false);
    }
  }

  async function persistEmbeddings() {
    if (!selectedFilename) {
      return;
    }

    setArtifactBusy(true);
    setArtifactMessage("");
    setDocumentsError("");

    try {
      const payload = await persistEmbeddingsRequest(selectedFilename);
      setEmbeddingArtifact(payload);
      setArtifactMessage("Persisted embeddings successfully.");
    } catch (error) {
      setDocumentsError(error instanceof Error ? error.message : "Failed to persist embeddings");
    } finally {
      setArtifactBusy(false);
    }
  }

  async function generatePipeline() {
    if (!selectedFilename) {
      return;
    }

    setArtifactBusy(true);
    setArtifactMessage("");
    setDocumentsError("");

    try {
      const chunkPayload = await persistChunksRequest(selectedFilename);
      setChunkArtifact(chunkPayload);

      const embeddingPayload = await persistEmbeddingsRequest(selectedFilename);
      setEmbeddingArtifact(embeddingPayload);

      setArtifactMessage("Generated chunks and embeddings successfully.");
    } catch (error) {
      setDocumentsError(error instanceof Error ? error.message : "Failed to generate pipeline");
    } finally {
      setArtifactBusy(false);
    }
  }

  async function loadEvaluationDatasets(refreshOverview = false) {
    setEvalError("");

    const [retrievalPayload, routePayload, workflowPayload, toolExecutionPayload, overviewPayload, metricsSummaryPayload] = await Promise.allSettled([
      fetchEvaluationDatasets(),
      fetchAgentRouteEvaluationDatasets(),
      fetchAgentWorkflowEvaluationDatasets(),
      fetchToolExecutionEvaluationDatasets(),
      fetchEvaluationOverview(refreshOverview),
      fetchEvaluationMetricsSummary(refreshOverview),
    ]);

    setDatasets(retrievalPayload.status === "fulfilled" ? retrievalPayload.value.datasets : []);
    setAgentRouteDatasets(routePayload.status === "fulfilled" ? routePayload.value.datasets : []);
    setAgentWorkflowDatasets(
      workflowPayload.status === "fulfilled" ? workflowPayload.value.datasets : [],
    );
    setToolExecutionDatasets(
      toolExecutionPayload.status === "fulfilled" ? toolExecutionPayload.value.datasets : [],
    );
    setEvaluationOverview(overviewPayload.status === "fulfilled" ? overviewPayload.value : null);
    setEvaluationMetricsSummary(
      metricsSummaryPayload.status === "fulfilled" ? metricsSummaryPayload.value : null,
    );

    const failures = [
      retrievalPayload.status === "rejected" ? "retrieval" : null,
      routePayload.status === "rejected" ? "agent-route" : null,
      workflowPayload.status === "rejected" ? "agent-workflow" : null,
      toolExecutionPayload.status === "rejected" ? "tool-execution" : null,
      overviewPayload.status === "rejected" ? "overview" : null,
      metricsSummaryPayload.status === "rejected" ? "metrics-summary" : null,
    ].filter((item): item is string => item !== null);

    if (failures.length > 0) {
      setEvalError(`Some evaluation datasets failed to load: ${failures.join(", ")}`);
    }

    setLatestEvalRevision((current) => current + 1);
  }

  useEffect(() => {
    const currentOptions = visibleDatasetOptions;
    if (currentOptions.length === 0) {
      setDatasetName("");
      return;
    }

    if (!currentOptions.some((item) => item.dataset_name === datasetName)) {
      setDatasetName(currentOptions[0].dataset_name);
    }
  }, [evaluationMode, datasetName, visibleDatasetOptions]);

  useEffect(() => {
    if (!datasetName) {
      return;
    }

    let cancelled = false;

    async function loadLatestEvaluationReport() {
      try {
        if (evaluationMode === "retrieval") {
          const [payload, historyPayload] = await Promise.all([
            fetchLatestEvaluation(datasetName, evalTopK),
            fetchEvaluationHistory(datasetName, evalTopK),
          ]);
          if (!cancelled) {
            setEvalResult(payload);
            setEvaluationHistory(historyPayload.entries);
          }
          return;
        }

        if (evaluationMode === "agent-route") {
          const [payload, historyPayload] = await Promise.all([
            fetchLatestAgentRouteEvaluation(datasetName),
            fetchAgentRouteEvaluationHistory(datasetName),
          ]);
          if (!cancelled) {
            setAgentRouteEvalResult(payload);
            setEvaluationHistory(historyPayload.entries);
          }
          return;
        }

        if (evaluationMode === "tool-execution") {
          const [payload, historyPayload] = await Promise.all([
            fetchLatestToolExecutionEvaluation(datasetName),
            fetchToolExecutionEvaluationHistory(datasetName),
          ]);
          if (!cancelled) {
            setToolExecutionEvalResult(payload);
            setEvaluationHistory(historyPayload.entries);
          }
          return;
        }

        const [payload, historyPayload] = await Promise.all([
          fetchLatestAgentWorkflowEvaluation(datasetName),
          fetchAgentWorkflowEvaluationHistory(datasetName),
        ]);
        if (!cancelled) {
          setAgentWorkflowEvalResult(payload);
          setEvaluationHistory(historyPayload.entries);
        }
      } catch {
        if (cancelled) {
          return;
        }

        if (evaluationMode === "retrieval") {
          setEvalResult(null);
        } else if (evaluationMode === "agent-route") {
          setAgentRouteEvalResult(null);
        } else if (evaluationMode === "tool-execution") {
          setToolExecutionEvalResult(null);
        } else {
          setAgentWorkflowEvalResult(null);
        }
        setEvaluationHistory([]);
      }
    }

    void loadLatestEvaluationReport();

    return () => {
      cancelled = true;
    };
  }, [datasetName, evalTopK, evaluationMode, latestEvalRevision]);

  async function submitQuery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setQueryBusy(true);
    setQueryError("");
    setQueryResult(null);
    setAgentQueryResult(null);

    try {
      const payload = await runQueryRequest(queryFilename, question, topK);
      setQueryResult(payload);
    } catch (error) {
      setQueryError(error instanceof Error ? error.message : "Failed to run query");
    } finally {
      setQueryBusy(false);
    }
  }

  async function runDiagnostics() {
    setQueryBusy(true);
    setQueryError("");
    setDiagnosticsResult(null);

    try {
      const payload = await runDiagnosticsRequest(queryFilename, question, topK);
      setDiagnosticsResult(payload);
    } catch (error) {
      setQueryError(error instanceof Error ? error.message : "Failed to run diagnostics");
    } finally {
      setQueryBusy(false);
    }
  }

  async function runAgentQuery() {
    setQueryBusy(true);
    setQueryError("");
    setAgentQueryResult(null);

    try {
      const payload = await runAgentQueryRequest(queryFilename, question, topK);
      setAgentQueryResult(payload);
      await loadAgentWorkflowRuns();
    } catch (error) {
      setQueryError(error instanceof Error ? error.message : "Failed to run agent workflow");
    } finally {
      setQueryBusy(false);
    }
  }

  async function loadAgentWorkflowRun(runId: string) {
    setQueryBusy(true);
    setQueryError("");
    setAgentQueryResult(null);

    try {
      const payload = await fetchAgentWorkflowRun(runId);
      setAgentQueryResult(payload);
    } catch (error) {
      setQueryError(error instanceof Error ? error.message : "Failed to load workflow run");
    } finally {
      setQueryBusy(false);
    }
  }

  async function recoverAgentWorkflowRun(
    runId: string,
    recoveryAction?: string,
    clarificationContext?: Record<string, string>,
  ) {
    setQueryBusy(true);
    setQueryError("");

    try {
      const payload = await recoverAgentWorkflowRunRequest(
        runId,
        recoveryAction,
        clarificationContext,
      );
      setAgentQueryResult(payload);
      await loadAgentWorkflowRuns();
    } catch (error) {
      setQueryError(error instanceof Error ? error.message : "Failed to recover workflow run");
    } finally {
      setQueryBusy(false);
    }
  }

  async function submitEvaluation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setEvalBusy(true);
    setEvalError("");
    setEvalResult(null);
    setAgentRouteEvalResult(null);
    setAgentWorkflowEvalResult(null);
    setToolExecutionEvalResult(null);

    try {
      if (evaluationMode === "retrieval") {
        const payload = await runEvaluationRequest(datasetName, evalTopK);
        setEvalResult(payload);
      } else if (evaluationMode === "agent-route") {
        const payload = await runAgentRouteEvaluationRequest(datasetName);
        setAgentRouteEvalResult(payload);
      } else if (evaluationMode === "tool-execution") {
        const payload = await runToolExecutionEvaluationRequest(datasetName);
        setToolExecutionEvalResult(payload);
      } else {
        const payload = await runAgentWorkflowEvaluationRequest(datasetName);
        setAgentWorkflowEvalResult(payload);
      }
    } catch (error) {
      setEvalError(error instanceof Error ? error.message : "Failed to run evaluation");
    } finally {
      setEvalBusy(false);
    }
  }

  async function exportEvaluationBundle() {
    setExportBusy(true);
    setEvalError("");

    try {
      const payload = await fetchEvaluationExportBundle();
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      });
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      const timestamp = payload.generated_at.replace(/[:.]/g, "-");
      anchor.href = url;
      anchor.download = `evaluation_bundle_${timestamp}.json`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      setEvalError(error instanceof Error ? error.message : "Failed to export evaluation bundle");
    } finally {
      setExportBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <div className="hero-topbar">
            <div>
              <p className="eyebrow">{appCopy.eyebrow}</p>
              <h1>{appCopy.brand}</h1>
            </div>
          </div>
          <p className="hero-copy">
            {appCopy.heroCopy}
          </p>
        </div>
        <div className="hero-side">
          <div className="locale-toggle" aria-label={appCopy.language}>
            <span className="locale-toggle-label">{appCopy.language}</span>
            <div className="locale-toggle-control">
              <button
                type="button"
                className={`locale-toggle-button${locale === "en" ? " active" : ""}`}
                onClick={() => setLocale("en")}
              >
                {appCopy.english}
              </button>
              <button
                type="button"
                className={`locale-toggle-button${locale === "zh" ? " active" : ""}`}
                onClick={() => setLocale("zh")}
              >
                {appCopy.chinese}
              </button>
            </div>
          </div>
          <div className="hero-stats">
            <div className="stat-card">
              <span>{appCopy.documents}</span>
              <strong>{documents.length}</strong>
            </div>
            <div className="stat-card">
              <span>{appCopy.evalDatasets}</span>
              <strong>
                {datasets.length +
                  agentRouteDatasets.length +
                  agentWorkflowDatasets.length +
                  toolExecutionDatasets.length}
              </strong>
            </div>
            <div className="stat-card">
              <span>{appCopy.defaultTopK}</span>
              <strong>{topK}</strong>
            </div>
          </div>
        </div>
      </header>

      <section className="status-banner-wrap" aria-label={appCopy.systemSnapshot}>
        <div className="status-banner-heading">
          <span className="section-label">{appCopy.systemSnapshot}</span>
          <p className="status-banner-copy">
            {appCopy.systemSnapshotCopy}
          </p>
        </div>
        <section className="status-banner">
          <div className="status-pill">
            <span>{appCopy.backend}</span>
            <strong>{systemHealth?.status ?? appCopy.unknown}</strong>
          </div>
          <div className="status-pill">
            <span>{appCopy.environment}</span>
            <strong>{systemHealth?.app_env ?? appCopy.unavailable}</strong>
          </div>
          <div className="status-pill">
            <span>{appCopy.embedding}</span>
            <strong>
              {systemHealth
                ? `${systemHealth.embedding_provider} / ${systemHealth.embedding_model}`
                : appCopy.unavailable}
            </strong>
          </div>
          <div className="status-pill">
            <span>{appCopy.chat}</span>
            <strong>
              {systemHealth
                ? `${systemHealth.chat_provider} / ${systemHealth.chat_model}`
                : appCopy.unavailable}
            </strong>
          </div>
          <div className="status-pill">
            <span>{appCopy.providerKeys}</span>
            <strong>
              {systemHealth
                ? `Gemini ${systemHealth.providers.gemini_configured ? appCopy.on : appCopy.off} | OpenAI ${systemHealth.providers.openai_configured ? appCopy.on : appCopy.off}`
                : appCopy.unavailable}
            </strong>
          </div>
          <div className="status-pill">
            <span>{appCopy.infra}</span>
            <strong>
              {systemHealth
                ? `DB ${systemHealth.storage.database_configured ? appCopy.on : appCopy.off} | Redis ${systemHealth.storage.redis_configured ? appCopy.on : appCopy.off}`
                : appCopy.unavailable}
            </strong>
          </div>
        </section>
      </section>
      {systemHealthError && <p className="error">{systemHealthError}</p>}

      <section className="nav-section" aria-label={appCopy.modules}>
        <div className="nav-section-heading">
          <span className="section-label">{appCopy.modules}</span>
          <p className="nav-section-copy">
            {appCopy.modulesCopy}
          </p>
        </div>
        <nav className="tab-row" aria-label="Views">
          {views.map((view) => (
            <button
              key={view.key}
              className={`tab-button${activeView === view.key ? " active" : ""}`}
              onClick={() => setActiveView(view.key)}
              type="button"
            >
              <span>{view.label}</span>
              <small>{view.kicker}</small>
            </button>
          ))}
        </nav>
      </section>

      {activeView === "documents" && (
        <DocumentsView
          locale={locale}
          documents={documents}
          selectedFilename={selectedFilename}
          preview={preview}
          chunkArtifact={chunkArtifact}
          embeddingArtifact={embeddingArtifact}
          documentsBusy={documentsBusy}
          artifactBusy={artifactBusy}
          uploadBusy={uploadBusy}
          documentsError={documentsError}
          artifactMessage={artifactMessage}
          uploadMessage={uploadMessage}
          onRefreshDocuments={() => void loadDocuments()}
          onSelectDocument={handleSelectDocument}
          onRefreshArtifacts={() => void loadArtifactStatus(selectedFilename)}
          onPersistChunks={() => void persistChunks()}
          onPersistEmbeddings={() => void persistEmbeddings()}
          onGeneratePipeline={() => void generatePipeline()}
          onDeleteDocument={() => void deleteDocument()}
          onUploadFile={(event) => {
            const file = event.target.files?.[0];
            if (file) {
              void uploadDocument(file);
            }
            event.target.value = "";
          }}
        />
      )}

      {activeView === "query" && (
        <QueryView
          locale={locale}
          documents={documents}
          queryFilename={queryFilename}
          question={question}
          topK={topK}
          activePresetQuestions={activePresetQuestions}
          queryResult={queryResult}
          agentQueryResult={agentQueryResult}
          agentWorkflowRuns={agentWorkflowRuns}
          diagnosticsResult={diagnosticsResult}
          queryError={queryError}
          queryBusy={queryBusy}
          onChangeDocument={handleChangeQueryDocument}
          onChangeQuestion={setQuestion}
          onChangeTopK={setTopK}
          onClearDiagnostics={() => setDiagnosticsResult(null)}
          onSubmitQuery={submitQuery}
          onRunAgent={() => void runAgentQuery()}
          onLoadAgentWorkflowRun={(runId) => void loadAgentWorkflowRun(runId)}
          onRecoverAgentWorkflowRun={(runId, recoveryAction, clarificationContext) =>
            void recoverAgentWorkflowRun(runId, recoveryAction, clarificationContext)
          }
          onRunDiagnostics={() => void runDiagnostics()}
        />
      )}

      {activeView === "evaluation" && (
        <EvaluationView
          locale={locale}
          evaluationMode={evaluationMode}
          evaluationOverview={evaluationOverview}
          evaluationMetricsSummary={evaluationMetricsSummary}
          datasets={datasets}
          agentRouteDatasets={agentRouteDatasets}
          agentWorkflowDatasets={agentWorkflowDatasets}
          toolExecutionDatasets={toolExecutionDatasets}
          datasetName={datasetName}
          evalTopK={evalTopK}
          evalResult={evalResult}
          agentRouteEvalResult={agentRouteEvalResult}
          agentWorkflowEvalResult={agentWorkflowEvalResult}
          toolExecutionEvalResult={toolExecutionEvalResult}
          evaluationHistory={evaluationHistory}
          evalError={evalError}
          evalBusy={evalBusy}
          evalCaseFilter={evalCaseFilter}
          filteredEvalCases={filteredEvalCases}
          filteredAgentRouteCases={filteredAgentRouteCases}
          filteredAgentWorkflowCases={filteredAgentWorkflowCases}
          exportBusy={exportBusy}
          onRefreshDatasets={() => void loadEvaluationDatasets(true)}
          onExportBundle={() => void exportEvaluationBundle()}
          onChangeEvaluationMode={setEvaluationMode}
          onChangeDatasetName={setDatasetName}
          onChangeEvalTopK={setEvalTopK}
          onSubmitEvaluation={submitEvaluation}
          onChangeEvalCaseFilter={setEvalCaseFilter}
        />
      )}
    </div>
  );
}

export default App;


