import type {
  AgentWorkflowResponse,
  DiagnosticsResponse,
  DocumentListResponse,
  DocumentPreview,
  EvalDatasetListResponse,
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
