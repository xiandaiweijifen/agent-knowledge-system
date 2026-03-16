from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    filename: str
    question: str
    top_k: int = 3


class QueryRouteRequest(BaseModel):
    question: str
    filename: str | None = None


class AgentQueryRequest(BaseModel):
    question: str
    filename: str | None = None
    top_k: int = 3
    debug_fault_injection: dict[str, object] = Field(default_factory=dict)


class AgentResumeRequest(BaseModel):
    original_question: str | None = None
    run_id: str | None = None
    clarification_context: dict[str, str] = Field(default_factory=dict)
    filename: str | None = None
    top_k: int = 3
    debug_fault_injection: dict[str, object] = Field(default_factory=dict)


class AgentRecoverRequest(BaseModel):
    run_id: str
    recovery_action: str | None = None
    clarification_context: dict[str, str] = Field(default_factory=dict)
    filename: str | None = None
    top_k: int = 3
    debug_fault_injection: dict[str, object] = Field(default_factory=dict)


class WorkflowTraceEvent(BaseModel):
    stage: str
    status: str
    timestamp: str
    detail: str


class WorkflowStepRecord(BaseModel):
    step_id: str
    step_index: int
    step_status: str
    attempt_count: int = 1
    retried: bool = False
    started_at: str
    completed_at: str | None = None
    question: str
    tool_plan: dict
    tool_execution: dict | None = None
    failure_message: str | None = None


class RouteDecision(BaseModel):
    route_type: str
    route_reason: str
    filename: str | None = None


class QueryDiagnosticsRequest(BaseModel):
    filename: str
    question: str
    top_k: int = 3
    candidate_count: int = 10


class RetrievedChunkMatch(BaseModel):
    chunk_id: str
    chunk_index: int
    source_filename: str
    source_suffix: str
    char_count: int
    content: str
    vector_score: float = 0.0
    rerank_bonus: float = 0.0
    score: float


class RetrievalResult(BaseModel):
    filename: str
    embedding_provider: str
    embedding_model: str
    vector_dim: int
    question: str
    top_k: int
    retrieved_at: str
    retrieval_latency_ms: float
    query_embedding_provider: str
    query_embedding_model: str
    matches: list[RetrievedChunkMatch] = Field(default_factory=list)


class QueryResponse(BaseModel):
    filename: str
    question: str
    answer: str
    answer_source: str
    model: str
    answered_at: str
    answer_latency_ms: float
    chat_provider: str
    chat_model: str
    retrieval: RetrievalResult


class RetrievalDiagnosticsSummary(BaseModel):
    total_scored_chunks: int
    returned_candidate_count: int
    max_score: float
    min_score: float
    mean_score: float


class QueryDiagnosticsResponse(BaseModel):
    filename: str
    question: str
    retrieval: RetrievalResult
    diagnostics: RetrievalDiagnosticsSummary
    candidates: list[RetrievedChunkMatch] = Field(default_factory=list)


class AgentWorkflowResponse(BaseModel):
    run_id: str | None = None
    root_run_id: str | None = None
    recovery_depth: int = 0
    question: str
    resumed_from_question: str | None = None
    source_run_id: str | None = None
    recovered_via_action: str | None = None
    resume_source_type: str | None = None
    resume_strategy: str | None = None
    resumed_from_step_index: int | None = None
    reused_step_indices: list[int] = Field(default_factory=list)
    applied_clarification_fields: list[str] = Field(default_factory=list)
    question_rewritten: bool = False
    overridden_plan_arguments: list[str] = Field(default_factory=list)
    workflow_status: str
    terminal_reason: str | None = None
    outcome_category: str | None = None
    is_recoverable: bool | None = None
    retry_state: str | None = None
    recommended_recovery_action: str | None = None
    available_recovery_actions: list[str] = Field(default_factory=list)
    recovery_action_details: dict[str, dict[str, object]] = Field(default_factory=dict)
    failure_stage: str | None = None
    failure_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    last_updated_at: str | None = None
    workflow_planning_mode: str | None = None
    tool_planning_mode: str | None = None
    tool_planning_modes: list[str] = Field(default_factory=list)
    clarification_planning_mode: str | None = None
    planner_call_count: int = 0
    tool_planner_call_count: int = 0
    workflow_planning_latency_ms: int = 0
    tool_planning_latency_ms: int = 0
    clarification_planning_latency_ms: int = 0
    planner_latency_ms_total: int = 0
    llm_planner_layers: list[str] = Field(default_factory=list)
    fallback_planner_layers: list[str] = Field(default_factory=list)
    llm_tool_planner_steps: list[int] = Field(default_factory=list)
    fallback_tool_planner_steps: list[int] = Field(default_factory=list)
    retry_count: int = 0
    retried_step_indices: list[int] = Field(default_factory=list)
    step_count: int = 0
    route: RouteDecision
    workflow_trace: list[WorkflowTraceEvent] = Field(default_factory=list)
    filename: str | None = None
    answer: str | None = None
    answer_source: str | None = None
    model: str | None = None
    answered_at: str | None = None
    answer_latency_ms: float | None = None
    chat_provider: str | None = None
    chat_model: str | None = None
    retrieval: RetrievalResult | None = None
    clarification_message: str | None = None
    clarification_plan: dict | None = None
    tool_plan: dict | None = None
    tool_execution: dict | None = None
    tool_chain: list[WorkflowStepRecord] = Field(default_factory=list)


class AgentWorkflowRunSummary(BaseModel):
    run_id: str
    root_run_id: str | None = None
    recovery_depth: int = 0
    question: str
    resumed_from_question: str | None = None
    source_run_id: str | None = None
    recovered_via_action: str | None = None
    resume_source_type: str | None = None
    resume_strategy: str | None = None
    resumed_from_step_index: int | None = None
    reused_step_indices: list[int] = Field(default_factory=list)
    applied_clarification_fields: list[str] = Field(default_factory=list)
    question_rewritten: bool = False
    overridden_plan_arguments: list[str] = Field(default_factory=list)
    workflow_status: str
    terminal_reason: str | None = None
    outcome_category: str | None = None
    is_recoverable: bool | None = None
    retry_state: str | None = None
    recommended_recovery_action: str | None = None
    available_recovery_actions: list[str] = Field(default_factory=list)
    recovery_action_details: dict[str, dict[str, object]] = Field(default_factory=dict)
    failure_stage: str | None = None
    failure_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    last_updated_at: str | None = None
    workflow_planning_mode: str | None = None
    tool_planning_mode: str | None = None
    tool_planning_modes: list[str] = Field(default_factory=list)
    clarification_planning_mode: str | None = None
    planner_call_count: int = 0
    tool_planner_call_count: int = 0
    workflow_planning_latency_ms: int = 0
    tool_planning_latency_ms: int = 0
    clarification_planning_latency_ms: int = 0
    planner_latency_ms_total: int = 0
    llm_planner_layers: list[str] = Field(default_factory=list)
    fallback_planner_layers: list[str] = Field(default_factory=list)
    llm_tool_planner_steps: list[int] = Field(default_factory=list)
    fallback_tool_planner_steps: list[int] = Field(default_factory=list)
    retry_count: int = 0
    retried_step_indices: list[int] = Field(default_factory=list)
    step_count: int = 0
    route_type: str
    route_reason: str
    filename: str | None = None
    answered_at: str | None = None
    answer_source: str | None = None
    final_tool_name: str | None = None
    final_tool_action: str | None = None


class AgentWorkflowRunListResponse(BaseModel):
    runs: list[AgentWorkflowRunSummary] = Field(default_factory=list)


class AgentWorkflowMigrationResponse(BaseModel):
    migrated_run_count: int
    migrated_step_count: int
    total_run_count: int


class AgentWorkflowRunStatsResponse(BaseModel):
    total_run_count: int
    completed_run_count: int
    clarification_required_run_count: int
    failed_run_count: int
    latest_run_id: str | None = None
    latest_updated_at: str | None = None


class AgentWorkflowRunPruneRequest(BaseModel):
    retain: int = 100


class AgentWorkflowRunPruneResponse(BaseModel):
    total_run_count_before: int
    retained_run_count: int
    removed_run_count: int


class AgentWorkflowRunResetRequest(BaseModel):
    confirm: bool = False


class AgentWorkflowRunResetResponse(BaseModel):
    removed_run_count: int
