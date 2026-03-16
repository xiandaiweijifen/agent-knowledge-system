import type {
  AgentWorkflowResponse,
  AgentWorkflowRunListResponse,
  AgentEvalDatasetListResponse,
  AgentRouteEvalReportResponse,
  AgentWorkflowEvalReportResponse,
  ToolExecutionEvalReportResponse,
  DiagnosticsResponse,
  DocumentListResponse,
  DocumentPreview,
  EvalDatasetListResponse,
  EvaluationReportHistoryResponse,
  EvaluationExportBundleResponse,
  EvaluationOverviewResponse,
  EvaluationMetricsSummaryResponse,
  EvalReportResponse,
  PersistedChunkDocument,
  PersistedEmbeddingDocument,
  QueryResponse,
  SystemHealthResponse,
  UploadDocumentResponse,
} from "./types";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function fetchDocuments() {
  return apiFetch<DocumentListResponse>("/api/documents");
}

export function fetchSystemHealth() {
  return apiFetch<SystemHealthResponse>("/api/health/system");
}

export function deleteDocument(filename: string) {
  return apiFetch<{
    filename: string;
    deleted_document: boolean;
    deleted_chunks: boolean;
    deleted_embeddings: boolean;
  }>(`/api/documents/${encodeURIComponent(filename)}`, {
    method: "DELETE",
  });
}

export async function uploadDocument(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/api/documents/upload", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<UploadDocumentResponse>;
}

export function fetchDocumentPreview(filename: string) {
  return apiFetch<DocumentPreview>(`/api/documents/${encodeURIComponent(filename)}`);
}

export function fetchPersistedChunks(filename: string) {
  return apiFetch<PersistedChunkDocument>(
    `/api/documents/${encodeURIComponent(filename)}/chunks/persisted`,
  );
}

export function fetchPersistedEmbeddings(filename: string) {
  return apiFetch<PersistedEmbeddingDocument>(
    `/api/documents/${encodeURIComponent(filename)}/embeddings/persisted`,
  );
}

export function persistChunks(filename: string) {
  return apiFetch<PersistedChunkDocument>(
    `/api/documents/${encodeURIComponent(filename)}/chunks/persist?chunk_size=500&chunk_overlap=100&chunk_strategy=paragraph`,
    {
      method: "POST",
    },
  );
}

export function persistEmbeddings(filename: string) {
  return apiFetch<PersistedEmbeddingDocument>(
    `/api/documents/${encodeURIComponent(filename)}/embeddings/persist`,
    {
      method: "POST",
    },
  );
}

export function runQuery(filename: string, question: string, topK: number) {
  return apiFetch<QueryResponse>("/api/query", {
    method: "POST",
    body: JSON.stringify({
      filename,
      question,
      top_k: topK,
    }),
  });
}

export function runDiagnostics(filename: string, question: string, topK: number) {
  return apiFetch<DiagnosticsResponse>("/api/query/diagnostics", {
    method: "POST",
    body: JSON.stringify({
      filename,
      question,
      top_k: topK,
      candidate_count: 10,
    }),
  });
}

export function runAgentQuery(filename: string, question: string, topK: number) {
  return apiFetch<AgentWorkflowResponse>("/api/query/agent", {
    method: "POST",
    body: JSON.stringify({
      filename: filename || null,
      question,
      top_k: topK,
    }),
  });
}

export function fetchAgentWorkflowRuns(limit = 10) {
  return apiFetch<AgentWorkflowRunListResponse>(`/api/query/agent/runs?limit=${limit}`);
}

export function fetchAgentWorkflowRun(runId: string) {
  return apiFetch<AgentWorkflowResponse>(`/api/query/agent/runs/${encodeURIComponent(runId)}`);
}

export function recoverAgentWorkflowRun(
  runId: string,
  recoveryAction?: string,
  clarificationContext?: Record<string, string>,
) {
  return apiFetch<AgentWorkflowResponse>("/api/query/agent/recover", {
    method: "POST",
    body: JSON.stringify({
      run_id: runId,
      recovery_action: recoveryAction ?? null,
      clarification_context: clarificationContext ?? {},
    }),
  });
}

export function fetchEvaluationDatasets() {
  return apiFetch<EvalDatasetListResponse>("/api/evaluation/retrieval/datasets");
}

export function runEvaluation(datasetName: string, topK: number) {
  return apiFetch<EvalReportResponse>("/api/evaluation/retrieval", {
    method: "POST",
    body: JSON.stringify({
      dataset_name: datasetName,
      top_k: topK,
    }),
  });
}

export function fetchLatestEvaluation(datasetName: string, topK: number) {
  const searchParams = new URLSearchParams({
    dataset_name: datasetName,
    top_k: String(topK),
  });
  return apiFetch<EvalReportResponse>(`/api/evaluation/retrieval/latest?${searchParams.toString()}`);
}

export function fetchEvaluationHistory(datasetName: string, topK: number, limit = 5) {
  const searchParams = new URLSearchParams({
    dataset_name: datasetName,
    top_k: String(topK),
    limit: String(limit),
  });
  return apiFetch<EvaluationReportHistoryResponse>(
    `/api/evaluation/retrieval/history?${searchParams.toString()}`,
  );
}

export function fetchAgentRouteEvaluationDatasets() {
  return apiFetch<AgentEvalDatasetListResponse>("/api/evaluation/agent-route/datasets");
}

export function runAgentRouteEvaluation(datasetName: string) {
  return apiFetch<AgentRouteEvalReportResponse>("/api/evaluation/agent-route", {
    method: "POST",
    body: JSON.stringify({
      dataset_name: datasetName,
    }),
  });
}

export function fetchLatestAgentRouteEvaluation(datasetName: string) {
  const searchParams = new URLSearchParams({
    dataset_name: datasetName,
  });
  return apiFetch<AgentRouteEvalReportResponse>(
    `/api/evaluation/agent-route/latest?${searchParams.toString()}`,
  );
}

export function fetchAgentRouteEvaluationHistory(datasetName: string, limit = 5) {
  const searchParams = new URLSearchParams({
    dataset_name: datasetName,
    limit: String(limit),
  });
  return apiFetch<EvaluationReportHistoryResponse>(
    `/api/evaluation/agent-route/history?${searchParams.toString()}`,
  );
}

export function fetchAgentWorkflowEvaluationDatasets() {
  return apiFetch<AgentEvalDatasetListResponse>("/api/evaluation/agent-workflow/datasets");
}

export function fetchToolExecutionEvaluationDatasets() {
  return apiFetch<AgentEvalDatasetListResponse>("/api/evaluation/tool-execution/datasets");
}

export function runAgentWorkflowEvaluation(datasetName: string) {
  return apiFetch<AgentWorkflowEvalReportResponse>("/api/evaluation/agent-workflow", {
    method: "POST",
    body: JSON.stringify({
      dataset_name: datasetName,
    }),
  });
}

export function runToolExecutionEvaluation(datasetName: string) {
  return apiFetch<ToolExecutionEvalReportResponse>("/api/evaluation/tool-execution", {
    method: "POST",
    body: JSON.stringify({
      dataset_name: datasetName,
    }),
  });
}

export function fetchLatestAgentWorkflowEvaluation(datasetName: string) {
  const searchParams = new URLSearchParams({
    dataset_name: datasetName,
  });
  return apiFetch<AgentWorkflowEvalReportResponse>(
    `/api/evaluation/agent-workflow/latest?${searchParams.toString()}`,
  );
}

export function fetchAgentWorkflowEvaluationHistory(datasetName: string, limit = 5) {
  const searchParams = new URLSearchParams({
    dataset_name: datasetName,
    limit: String(limit),
  });
  return apiFetch<EvaluationReportHistoryResponse>(
    `/api/evaluation/agent-workflow/history?${searchParams.toString()}`,
  );
}

export function fetchLatestToolExecutionEvaluation(datasetName: string) {
  const searchParams = new URLSearchParams({
    dataset_name: datasetName,
  });
  return apiFetch<ToolExecutionEvalReportResponse>(
    `/api/evaluation/tool-execution/latest?${searchParams.toString()}`,
  );
}

export function fetchToolExecutionEvaluationHistory(datasetName: string, limit = 5) {
  const searchParams = new URLSearchParams({
    dataset_name: datasetName,
    limit: String(limit),
  });
  return apiFetch<EvaluationReportHistoryResponse>(
    `/api/evaluation/tool-execution/history?${searchParams.toString()}`,
  );
}

export function fetchEvaluationOverview(refresh = false) {
  const searchParams = new URLSearchParams();
  if (refresh) {
    searchParams.set("refresh", "true");
  }
  const suffix = searchParams.toString() ? `?${searchParams.toString()}` : "";
  return apiFetch<EvaluationOverviewResponse>(`/api/evaluation/overview${suffix}`);
}

export function fetchEvaluationMetricsSummary(refresh = false) {
  const searchParams = new URLSearchParams();
  if (refresh) {
    searchParams.set("refresh", "true");
  }
  const suffix = searchParams.toString() ? `?${searchParams.toString()}` : "";
  return apiFetch<EvaluationMetricsSummaryResponse>(`/api/evaluation/metrics-summary${suffix}`);
}

export function fetchEvaluationExportBundle(refresh = false) {
  const searchParams = new URLSearchParams();
  if (refresh) {
    searchParams.set("refresh", "true");
  }
  const suffix = searchParams.toString() ? `?${searchParams.toString()}` : "";
  return apiFetch<EvaluationExportBundleResponse>(`/api/evaluation/export-bundle${suffix}`);
}
