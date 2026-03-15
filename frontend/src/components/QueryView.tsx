import type { FormEvent } from "react";

import type {
  AgentWorkflowResponse,
  AgentWorkflowRunSummary,
  DiagnosticsResponse,
  DocumentItem,
  QueryResponse,
  ToolChainStep,
} from "../types";

type QueryViewProps = {
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
  onRunDiagnostics: () => void;
};

export function QueryView({
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
  onRunDiagnostics,
}: QueryViewProps) {
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
        <span className="section-label">Supporting Context</span>
        <div className="trace-grid">
          {supportingQuery && (
            <div>
              <span className="trace-label">Search Query</span>
              <strong>{supportingQuery}</strong>
            </div>
          )}
          {supportingMatchCount && (
            <div>
              <span className="trace-label">Matched Documents</span>
              <strong>{supportingMatchCount}</strong>
            </div>
          )}
        </div>
        {supportingDocuments && (
          <div className="supporting-block">
            <span className="trace-label">Documents</span>
            <p>{supportingDocuments}</p>
          </div>
        )}
        {supportingSnippets && (
          <div className="supporting-block">
            <span className="trace-label">Search Snippets</span>
            <p>{supportingSnippets}</p>
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
            <span className="trace-label">Execution Status</span>
            <strong>{toolExecution.execution_status}</strong>
          </div>
          <div>
            <span className="trace-label">Mode</span>
            <strong>{toolExecution.execution_mode}</strong>
          </div>
          <div>
            <span className="trace-label">Trace Id</span>
            <strong>{toolExecution.trace_id}</strong>
          </div>
        </div>
        <p className="subsection-copy">{toolExecution.result_summary}</p>
        {toolExecution.tool_name === "ticketing" && toolExecution.action !== "list" && (
          <div className="ticketing-highlight">
            <div className="trace-grid">
              <div>
                <span className="trace-label">Ticket Id</span>
                <strong>{toolExecution.output.ticket_id ?? "n/a"}</strong>
              </div>
              <div>
                <span className="trace-label">Status</span>
                <strong>{toolExecution.output.status ?? "n/a"}</strong>
              </div>
              <div>
                <span className="trace-label">Severity</span>
                <strong>{toolExecution.output.severity ?? "n/a"}</strong>
              </div>
              <div>
                <span className="trace-label">Environment</span>
                <strong>{toolExecution.output.environment ?? "n/a"}</strong>
              </div>
            </div>
          </div>
        )}
        {toolExecution.tool_name === "ticketing" && renderSupportingContext(toolExecution.output)}
        {toolExecution.tool_name === "ticketing" && toolExecution.action === "list" && (
          <div className="ticketing-highlight">
            <div className="trace-grid">
              <div>
                <span className="trace-label">Ticket Count</span>
                <strong>{toolExecution.output.ticket_count ?? "0"}</strong>
              </div>
              <div>
                <span className="trace-label">Status Filter</span>
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
              <p className="subsection-copy">No tickets matched the current filter.</p>
            )}
          </div>
        )}
        {Object.keys(toolExecution.output).length > 0 &&
          !(toolExecution.tool_name === "ticketing" && toolExecution.action === "list") && (
            <>
              <span className="section-label">Tool Output</span>
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

  return (
    <section className="panel-grid query-layout">
      <article className="panel panel-span view-banner">
        <div className="view-banner-content">
          <div>
            <span className="section-label">Query Workspace</span>
            <h2 className="view-banner-title">Answer Tracing And Retrieval Inspection</h2>
            <p className="view-banner-copy">
              Run grounded queries, compare answer traces, and inspect vector score versus rerank
              bonus behavior.
            </p>
          </div>
          <div className="view-banner-meta">
            <span>{queryFilename || "no document"}</span>
            <span>top-k {topK}</span>
            <span>{queryResult ? "answer ready" : "answer idle"}</span>
            <span>{diagnosticsResult ? "diagnostics ready" : "diagnostics idle"}</span>
          </div>
        </div>
      </article>

      <article className="panel">
        <div className="panel-heading">
          <div>
            <h2>Query Lab</h2>
            <p className="panel-intro">
              Probe retrieval behavior, answer generation, and reranking signals for a selected document.
            </p>
          </div>
          <button type="button" className="ghost-button" onClick={onClearDiagnostics}>
            Clear Diagnostics
          </button>
        </div>
        <form className="stack-form" onSubmit={onSubmitQuery}>
          <label>
            Document Context
            <select
              value={queryFilename}
              onChange={(event) => onChangeDocument(event.target.value)}
              disabled={documents.length === 0}
            >
              <option value="">No document context (Agent optional)</option>
              {documents.map((item) => (
                <option key={item.filename} value={item.filename}>
                  {item.filename}
                </option>
              ))}
            </select>
          </label>
          <p className="muted">
            `Run Query` and `Run Diagnostics` require a document. `Run Agent` can operate without one
            for tool execution or clarification workflows.
          </p>
          <label>
            Question
            <textarea value={question} onChange={(event) => onChangeQuestion(event.target.value)} rows={4} />
          </label>
          <div className="preset-block">
            <span className="section-label">Preset Questions</span>
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
            Top-K
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
              Run Query
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={queryBusy || !hasDocument || !hasQuestion}
              onClick={onRunDiagnostics}
            >
              Run Diagnostics
            </button>
            <button
              type="button"
              className="ghost-button"
              disabled={queryBusy || !hasQuestion}
              onClick={onRunAgent}
            >
              Run Agent
            </button>
          </div>
        </form>
        {!hasDocument && (
          <p className="muted">
            No document context selected. Retrieval-only actions are disabled, but agent tool workflows can
            still run.
          </p>
        )}
        {queryBusy && <p className="status">Running query workflow...</p>}
        {queryError && <p className="error">{queryError}</p>}
      </article>

      <div className="query-results">
        <article className="panel">
          <div className="panel-heading">
            <h2>Agent Workflow</h2>
          </div>
          {agentQueryResult ? (
            <div className="result-stack">
              <div className="trace-grid">
                <div>
                  <span className="trace-label">Workflow Status</span>
                  <strong>{agentQueryResult.workflow_status}</strong>
                </div>
                <div>
                  <span className="trace-label">Route</span>
                  <strong>{agentQueryResult.route.route_type}</strong>
                </div>
                <div>
                  <span className="trace-label">Answer Provider</span>
                  <strong>{agentQueryResult.chat_provider ?? "not used"}</strong>
                </div>
                <div>
                  <span className="trace-label">Tool</span>
                  <strong>{agentQueryResult.tool_plan?.tool_name ?? "not used"}</strong>
                </div>
              </div>

              <article className="subsection-card">
                <span className="section-label">Route Reason</span>
                <p className="subsection-copy">{agentQueryResult.route.route_reason}</p>
              </article>

              <article className="subsection-card">
                <span className="section-label">Route Context</span>
                <div className="pill-strip">
                  <span className={`meta-pill${routeUsesFilename ? "" : " muted-pill"}`}>
                    document {routeUsesFilename ? `used: ${agentQueryResult.filename}` : "not used"}
                  </span>
                  <span className={`meta-pill${routeUsesRetrieval ? "" : " muted-pill"}`}>
                    retrieval {routeUsesRetrieval ? "used" : "not used"}
                  </span>
                  <span className={`meta-pill${routeUsesToolPlanning ? "" : " muted-pill"}`}>
                    tool planning {routeUsesToolPlanning ? "used" : "not used"}
                  </span>
                </div>
              </article>

              <article className="subsection-card">
                <span className="section-label">Workflow Record</span>
                <div className="trace-grid">
                  <div>
                    <span className="trace-label">Run Id</span>
                    <strong>{agentQueryResult.run_id ?? "not persisted"}</strong>
                  </div>
                  <div>
                    <span className="trace-label">Resumed From</span>
                    <strong>{agentQueryResult.resumed_from_question ?? "not resumed"}</strong>
                  </div>
                  <div>
                    <span className="trace-label">Source Run</span>
                    <strong>{agentQueryResult.source_run_id ?? "not linked"}</strong>
                  </div>
                </div>
              </article>

              {agentQueryResult.answer && (
                <article className="subsection-card">
                  <span className="section-label">Knowledge Result</span>
                  <blockquote className="answer-card">{agentQueryResult.answer}</blockquote>
                </article>
              )}

              {hasToolChain && (
                <article className="subsection-card">
                  <span className="section-label">Executed Steps</span>
                  <p className="subsection-copy">
                    The workflow executed {agentQueryResult.tool_chain.length} step
                    {agentQueryResult.tool_chain.length === 1 ? "" : "s"} before returning the final result.
                  </p>
                  <div className="tool-chain-list">
                    {agentQueryResult.tool_chain.map((step, index) => (
                      <article
                        key={`${step.question}-${index + 1}`}
                        className="tool-chain-card"
                      >
                        <header className="tool-chain-header">
                          <div>
                            <span className="section-label">Step {index + 1}</span>
                            <h3>{step.tool_plan.tool_name}</h3>
                          </div>
                          <span className="status-chip success">
                            {step.tool_plan.action}
                          </span>
                        </header>
                        <p className="subsection-copy">
                          <strong>Question:</strong> {step.question}
                        </p>
                        <div className="trace-grid">
                          <div>
                            <span className="trace-label">Target</span>
                            <strong>{step.tool_plan.target}</strong>
                          </div>
                          <div>
                            <span className="trace-label">Planning Mode</span>
                            <strong>{step.tool_plan.planning_mode}</strong>
                          </div>
                          <div>
                            <span className="trace-label">Execution Mode</span>
                            <strong>{step.tool_execution.execution_mode}</strong>
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
                    {hasToolChain ? "Final Step" : "Tool Plan"}
                  </span>
                  <div className="trace-grid">
                    <div>
                      <span className="trace-label">Tool</span>
                      <strong>{agentQueryResult.tool_plan.tool_name}</strong>
                    </div>
                    <div>
                      <span className="trace-label">Action</span>
                      <strong>{agentQueryResult.tool_plan.action}</strong>
                    </div>
                    <div>
                      <span className="trace-label">Target</span>
                      <strong>{agentQueryResult.tool_plan.target}</strong>
                    </div>
                    <div>
                      <span className="trace-label">Planning Mode</span>
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
                    <p className="muted">
                      This top-level snapshot shows the final executed step. Use Executed Steps above
                      to inspect the full chain.
                    </p>
                  )}
                </article>
              )}

              {agentQueryResult.tool_execution && (
                <article className="subsection-card">
                  <span className="section-label">
                    {hasToolChain ? "Final Step Execution" : "Tool Execution"}
                  </span>
                  {renderToolExecutionDetails(agentQueryResult.tool_execution)}
                </article>
              )}

              {agentQueryResult.clarification_plan && (
                <article className="subsection-card">
                  <span className="section-label">Clarification Plan</span>
                  <p className="subsection-copy">
                    {agentQueryResult.clarification_message ??
                      agentQueryResult.clarification_plan.clarification_summary}
                  </p>
                  {agentQueryResult.clarification_plan.missing_fields.length > 0 && (
                    <div className="pill-strip">
                      {agentQueryResult.clarification_plan.missing_fields.map((field) => (
                        <span key={field} className="meta-pill">
                          missing: {field}
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

              <div className="section-label">Workflow Trace</div>
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
              <strong>No agent workflow yet</strong>
              <p>
                Run Agent to inspect route selection, workflow trace, and tool or clarification output.
              </p>
            </div>
          )}
        </article>

        <article className="panel">
          <div className="panel-heading">
            <h2>Recent Workflow Runs</h2>
          </div>
          {agentWorkflowRuns.length > 0 ? (
            <div className="run-list">
              {agentWorkflowRuns.map((run) => (
                <button
                  key={run.run_id}
                  type="button"
                  className="run-card"
                  onClick={() => onLoadAgentWorkflowRun(run.run_id)}
                >
                  <div className="card-title-row">
                    <strong>{run.question}</strong>
                    <span className="status-chip">{run.workflow_status}</span>
                  </div>
                  <div className="meta-row">
                    <span>route {run.route_type}</span>
                    <span>run {run.run_id}</span>
                  </div>
                  {run.resumed_from_question && (
                    <p className="subsection-copy">resumed from: {run.resumed_from_question}</p>
                  )}
                </button>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <strong>No workflow history yet</strong>
              <p>Run Agent to persist workflow runs, then load a recent run from this panel.</p>
            </div>
          )}
        </article>

        <article className="panel">
          <div className="panel-heading">
            <h2>Answer Trace</h2>
          </div>
          {queryResult ? (
            <div className="result-stack">
              <div className="trace-grid">
                <div>
                  <span className="trace-label">Chat Provider</span>
                  <strong>{queryResult.chat_provider}</strong>
                </div>
                <div>
                  <span className="trace-label">Chat Model</span>
                  <strong>{queryResult.chat_model}</strong>
                </div>
                <div>
                  <span className="trace-label">Answer Latency</span>
                  <strong>{queryResult.answer_latency_ms.toFixed(3)} ms</strong>
                </div>
                <div>
                  <span className="trace-label">Embedding Provider</span>
                  <strong>{queryResult.retrieval.embedding_provider}</strong>
                </div>
                <div>
                  <span className="trace-label">Query Provider</span>
                  <strong>{queryResult.retrieval.query_embedding_provider}</strong>
                </div>
                <div>
                  <span className="trace-label">Retrieval Latency</span>
                  <strong>{queryResult.retrieval.retrieval_latency_ms.toFixed(3)} ms</strong>
                </div>
              </div>
              <blockquote className="answer-card">{queryResult.answer}</blockquote>
              <div className="section-label">Top Retrieved Chunks</div>
              <div className="match-list compact">
                {queryResult.retrieval.matches.map((match) => (
                  <article key={match.chunk_id} className="match-card trace-card">
                    <header>
                      <strong>{match.chunk_id}</strong>
                      <span>{match.score.toFixed(6)}</span>
                    </header>
                    <div className="meta-row">
                      <span>chars {match.char_count}</span>
                      <span>vector {match.vector_score?.toFixed(6) ?? "-"}</span>
                      <span>bonus {match.rerank_bonus?.toFixed(6) ?? "-"}</span>
                    </div>
                    <p>{match.content}</p>
                  </article>
                ))}
              </div>
            </div>
          ) : (
            <div className="empty-state empty-state-large">
              <strong>No answer trace yet</strong>
              <p>Run a query to inspect answer text, provider selection, and top retrieved chunks.</p>
            </div>
          )}
        </article>

        <article className="panel">
          <div className="panel-heading">
            <h2>Retrieval Diagnostics</h2>
          </div>
          {diagnosticsResult ? (
            <>
              <div className="trace-grid">
                <div>
                  <span className="trace-label">Scored Chunks</span>
                  <strong>{diagnosticsResult.diagnostics.total_scored_chunks}</strong>
                </div>
                <div>
                  <span className="trace-label">Candidates</span>
                  <strong>{diagnosticsResult.diagnostics.returned_candidate_count}</strong>
                </div>
                <div>
                  <span className="trace-label">Mean Score</span>
                  <strong>{diagnosticsResult.diagnostics.mean_score.toFixed(6)}</strong>
                </div>
                <div>
                  <span className="trace-label">Max Score</span>
                  <strong>{diagnosticsResult.diagnostics.max_score.toFixed(6)}</strong>
                </div>
                <div>
                  <span className="trace-label">Min Score</span>
                  <strong>{diagnosticsResult.diagnostics.min_score.toFixed(6)}</strong>
                </div>
                <div>
                  <span className="trace-label">Latency</span>
                  <strong>{diagnosticsResult.retrieval.retrieval_latency_ms.toFixed(3)} ms</strong>
                </div>
              </div>
              <div className="section-label">Candidate Ranking</div>
              <div className="match-list compact">
                {diagnosticsResult.candidates.map((match) => (
                  <article key={match.chunk_id} className="match-card diagnostic trace-card">
                    <header>
                      <strong>{match.chunk_id}</strong>
                      <span>{match.score.toFixed(6)}</span>
                    </header>
                    <div className="meta-row">
                      <span>vector {match.vector_score?.toFixed(6) ?? "-"}</span>
                      <span>bonus {match.rerank_bonus?.toFixed(6) ?? "-"}</span>
                      <span>chars {match.char_count}</span>
                    </div>
                    <p>{match.content}</p>
                  </article>
                ))}
              </div>
            </>
          ) : (
            <div className="empty-state empty-state-large">
              <strong>No diagnostics yet</strong>
              <p>Run diagnostics to inspect vector scores, rerank bonuses, and candidate ordering.</p>
            </div>
          )}
        </article>
      </div>
    </section>
  );
}
