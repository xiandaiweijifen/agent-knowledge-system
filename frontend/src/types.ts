export type ViewKey = "documents" | "query" | "evaluation";

export type DocumentItem = {
  filename: string;
  size_bytes: number;
  suffix: string;
};

export type DocumentListResponse = {
  count: number;
  documents: DocumentItem[];
};

export type DocumentPreview = {
  filename: string;
  suffix: string;
  size_bytes: number;
  content: string;
};

export type UploadDocumentResponse = {
  filename: string;
  content_type: string | null;
  size_bytes: number;
  saved_path: string;
  message: string;
};

export type PersistedChunkDocument = {
  filename: string;
  suffix: string;
  source_path: string;
  created_at: string;
  pipeline_version: string;
  chunk_strategy: string;
  chunk_count: number;
  chunk_size: number;
  chunk_overlap: number;
};

export type PersistedEmbeddingDocument = {
  filename: string;
  suffix: string;
  source_path: string;
  source_chunk_path: string;
  created_at: string;
  pipeline_version: string;
  embedding_provider: string;
  embedding_model: string;
  vector_dim: number;
  chunk_count: number;
};

export type RetrievalMatch = {
  chunk_id: string;
  chunk_index: number;
  source_filename: string;
  source_suffix: string;
  char_count: number;
  content: string;
  score: number;
  vector_score?: number;
  rerank_bonus?: number;
};

export type RetrievalResponse = {
  filename: string;
  embedding_provider: string;
  embedding_model: string;
  vector_dim: number;
  question: string;
  top_k: number;
  retrieved_at: string;
  retrieval_latency_ms: number;
  query_embedding_provider: string;
  query_embedding_model: string;
  matches: RetrievalMatch[];
};

export type QueryResponse = {
  filename: string;
  question: string;
  answer: string;
  answer_source: string;
  model: string;
  answered_at: string;
  answer_latency_ms: number;
  chat_provider: string;
  chat_model: string;
  retrieval: RetrievalResponse;
};

export type DiagnosticsResponse = {
  filename: string;
  question: string;
  retrieval: RetrievalResponse;
  diagnostics: {
    total_scored_chunks: number;
    returned_candidate_count: number;
    max_score: number;
    min_score: number;
    mean_score: number;
  };
  candidates: RetrievalMatch[];
};

export type EvalDatasetInfo = {
  dataset_name: string;
  case_count: number;
  filenames: string[];
};

export type EvalDatasetListResponse = {
  datasets: EvalDatasetInfo[];
};

export type EvalReportResponse = {
  dataset_name: string;
  report: {
    top_k: number;
    summary: {
      total_cases: number;
      hit_rate_at_k: number;
      mean_reciprocal_rank: number;
    };
    cases: Array<{
      case_id: string;
      filename: string;
      question: string;
      expected_chunk_ids: string[];
      retrieved_chunk_ids: string[];
      hit_at_k: boolean;
      reciprocal_rank: number;
    }>;
  };
};

export type EvalCaseFilter = "all" | "hit" | "miss";
