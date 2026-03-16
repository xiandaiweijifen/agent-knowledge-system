export type Locale = "en" | "zh";

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

export type SystemHealthResponse = {
  status: string;
  app_env: string;
  embedding_provider: string;
  embedding_model: string;
  chat_provider: string;
  chat_model: string;
  providers: {
    gemini_configured: boolean;
    openai_configured: boolean;
  };
  storage: {
    database_configured: boolean;
    redis_configured: boolean;
  };
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

export type WorkflowTraceEvent = {
  stage: string;
  status: string;
  timestamp: string;
  detail: string;
};

export type RouteDecision = {
  route_type: string;
  route_reason: string;
  filename?: string | null;
};

export type ClarificationPlan = {
  question: string;
  planning_mode: string;
  missing_fields: string[];
  follow_up_questions: string[];
  clarification_summary: string;
};

export type ToolPlan = {
  question: string;
  planning_mode: string;
  route_hint: string;
  tool_name: string;
  action: string;
  target: string;
  arguments: Record<string, string>;
  plan_summary: string;
};

export type ToolExecution = {
  tool_name: string;
  action: string;
  target: string;
  execution_status: string;
  execution_mode: string;
  result_summary: string;
  trace_id: string;
  executed_at: string;
  output: Record<string, string>;
};

export type ToolChainStep = {
  step_id: string;
  step_index: number;
  step_status: string;
  attempt_count: number;
  retried: boolean;
  started_at: string;
  completed_at?: string | null;
  question: string;
  tool_plan: ToolPlan;
  tool_execution: ToolExecution | null;
  failure_message?: string | null;
};

export type RecoveryActionDetailValue =
  | string
  | number
  | boolean
  | null
  | number[]
  | string[];

export type RecoveryActionDetails = Record<string, Record<string, RecoveryActionDetailValue>>;

export type AgentWorkflowResponse = {
  run_id?: string | null;
  root_run_id?: string | null;
  recovery_depth?: number;
  question: string;
  resumed_from_question?: string | null;
  source_run_id?: string | null;
  recovered_via_action?: string | null;
  resume_source_type?: string | null;
  resume_strategy?: string | null;
  resumed_from_step_index?: number | null;
  reused_step_indices?: number[];
  applied_clarification_fields?: string[];
  question_rewritten?: boolean;
  overridden_plan_arguments?: string[];
  workflow_status: string;
  terminal_reason?: string | null;
  outcome_category?: string | null;
  is_recoverable?: boolean | null;
  retry_state?: string | null;
  recommended_recovery_action?: string | null;
  available_recovery_actions?: string[];
  recovery_action_details?: RecoveryActionDetails;
  failure_stage?: string | null;
  failure_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  last_updated_at?: string | null;
  workflow_planning_mode?: string | null;
  tool_planning_mode?: string | null;
  tool_planning_modes?: string[];
  clarification_planning_mode?: string | null;
  planner_call_count?: number;
  tool_planner_call_count?: number;
  workflow_planning_latency_ms?: number;
  tool_planning_latency_ms?: number;
  clarification_planning_latency_ms?: number;
  planner_latency_ms_total?: number;
  llm_planner_layers?: string[];
  fallback_planner_layers?: string[];
  llm_tool_planner_steps?: number[];
  fallback_tool_planner_steps?: number[];
  retry_count?: number;
  retried_step_indices?: number[];
  step_count?: number;
  route: RouteDecision;
  workflow_trace: WorkflowTraceEvent[];
  filename?: string | null;
  answer?: string | null;
  answer_source?: string | null;
  model?: string | null;
  answered_at?: string | null;
  answer_latency_ms?: number | null;
  chat_provider?: string | null;
  chat_model?: string | null;
  retrieval?: RetrievalResponse | null;
  clarification_message?: string | null;
  clarification_plan?: ClarificationPlan | null;
  tool_plan?: ToolPlan | null;
  tool_execution?: ToolExecution | null;
  tool_chain: ToolChainStep[];
};

export type AgentWorkflowRunSummary = {
  run_id: string;
  root_run_id?: string | null;
  recovery_depth?: number;
  question: string;
  resumed_from_question?: string | null;
  source_run_id?: string | null;
  recovered_via_action?: string | null;
  resume_source_type?: string | null;
  resume_strategy?: string | null;
  resumed_from_step_index?: number | null;
  reused_step_indices?: number[];
  applied_clarification_fields?: string[];
  question_rewritten?: boolean;
  overridden_plan_arguments?: string[];
  workflow_status: string;
  terminal_reason?: string | null;
  outcome_category?: string | null;
  is_recoverable?: boolean | null;
  retry_state?: string | null;
  recommended_recovery_action?: string | null;
  available_recovery_actions?: string[];
  recovery_action_details?: RecoveryActionDetails;
  failure_stage?: string | null;
  failure_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  last_updated_at?: string | null;
  workflow_planning_mode?: string | null;
  tool_planning_mode?: string | null;
  tool_planning_modes?: string[];
  clarification_planning_mode?: string | null;
  planner_call_count?: number;
  tool_planner_call_count?: number;
  workflow_planning_latency_ms?: number;
  tool_planning_latency_ms?: number;
  clarification_planning_latency_ms?: number;
  planner_latency_ms_total?: number;
  llm_planner_layers?: string[];
  fallback_planner_layers?: string[];
  llm_tool_planner_steps?: number[];
  fallback_tool_planner_steps?: number[];
  retry_count?: number;
  retried_step_indices?: number[];
  step_count?: number;
  route_type: string;
  route_reason: string;
  filename?: string | null;
  answered_at?: string | null;
  answer_source?: string | null;
  final_tool_name?: string | null;
  final_tool_action?: string | null;
};

export type AgentWorkflowRunListResponse = {
  runs: AgentWorkflowRunSummary[];
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

export type AgentEvalDatasetInfo = {
  dataset_name: string;
  case_count: number;
};

export type AgentEvalDatasetListResponse = {
  datasets: AgentEvalDatasetInfo[];
};

export type EvaluationReportHistoryEntry = {
  dataset_name: string;
  saved_at: string;
  report_source: string;
  top_k?: number | null;
  primary_metric_name: string;
  primary_metric_value: number;
  case_count: number;
};

export type EvaluationReportHistoryResponse = {
  entries: EvaluationReportHistoryEntry[];
};

export type EvalReportResponse = {
  dataset_name: string;
  saved_at?: string | null;
  report_source?: string | null;
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

export type AgentRouteEvalReportResponse = {
  dataset_name: string;
  saved_at?: string | null;
  report_source?: string | null;
  report: {
    summary: {
      total_cases: number;
      route_accuracy: number;
    };
    cases: Array<{
      case_id: string;
      question: string;
      filename?: string | null;
      expected_route_type: string;
      actual_route_type: string;
      route_reason: string;
      matched: boolean;
    }>;
  };
};

export type AgentWorkflowEvalReportResponse = {
  dataset_name: string;
  saved_at?: string | null;
  report_source?: string | null;
  report: {
    summary: {
      total_cases: number;
      workflow_accuracy: number;
    };
    cases: Array<{
      case_id: string;
      question: string;
      filename?: string | null;
      expected_route_type: string;
      actual_route_type: string;
      expected_workflow_status: string;
      actual_workflow_status: string;
      route_reason: string;
      matched: boolean;
    }>;
  };
};

export type ToolExecutionEvalReportResponse = {
  dataset_name: string;
  saved_at?: string | null;
  report_source?: string | null;
  report: {
    summary: {
      total_cases: number;
      tool_accuracy: number;
    };
    cases: Array<{
      case_id: string;
      question: string;
      expected_tool_name: string;
      actual_tool_name: string;
      expected_action: string;
      actual_action: string;
      expected_execution_status: string;
      actual_execution_status: string;
      matched: boolean;
      argument_matches: Record<string, boolean>;
      output_matches: Record<string, boolean>;
      output_key_matches: Record<string, boolean>;
    }>;
  };
};

export type EvaluationOverviewResponse = {
  generated_at: string;
  cache_status: string;
  retrieval: {
    dataset_count: number;
    total_cases: number;
    mean_hit_rate_at_k: number;
    mean_reciprocal_rank: number;
    best_dataset_name?: string | null;
    best_hit_rate_at_k: number;
  };
  workflow: {
    total_run_count: number;
    completed_run_count: number;
    clarification_required_run_count: number;
    failed_run_count: number;
    completion_rate: number;
    clarification_rate: number;
    failed_rate: number;
  };
  recovery: {
    recovered_run_count: number;
    recovered_completed_run_count: number;
    recovery_success_rate: number;
    average_recovery_depth: number;
    resume_from_failed_step_count: number;
    manual_retrigger_count: number;
    clarification_recovery_count: number;
  };
};

export type EvaluationMetricsSummaryResponse = {
  generated_at: string;
  cache_status: string;
  highlights: Array<{
    label: string;
    value: string;
    detail?: string | null;
  }>;
  sections: Array<{
    title: string;
    dataset_name?: string | null;
    metric_name: string;
    metric_value: number;
    formatted_value: string;
    detail?: string | null;
  }>;
};

export type EvaluationExportBundleResponse = {
  generated_at: string;
  overview: EvaluationOverviewResponse;
  metrics_summary: EvaluationMetricsSummaryResponse;
  reports: {
    retrieval: {
      dataset_name: string;
      top_k?: number | null;
      latest_report?: Record<string, unknown> | null;
      history: EvaluationReportHistoryEntry[];
    };
    agent_route: {
      dataset_name: string;
      top_k?: number | null;
      latest_report?: Record<string, unknown> | null;
      history: EvaluationReportHistoryEntry[];
    };
    agent_workflow: {
      dataset_name: string;
      top_k?: number | null;
      latest_report?: Record<string, unknown> | null;
      history: EvaluationReportHistoryEntry[];
    };
    tool_execution: {
      dataset_name: string;
      top_k?: number | null;
      latest_report?: Record<string, unknown> | null;
      history: EvaluationReportHistoryEntry[];
    };
  };
};

export type EvalCaseFilter = "all" | "hit" | "miss";
export type EvaluationMode = "retrieval" | "agent-route" | "agent-workflow" | "tool-execution";
