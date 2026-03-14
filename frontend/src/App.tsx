import { FormEvent, useEffect, useState } from "react";
import {
  fetchDocumentPreview,
  fetchDocuments,
  fetchEvaluationDatasets,
  fetchPersistedChunks,
  fetchPersistedEmbeddings,
  persistChunks as persistChunksRequest,
  persistEmbeddings as persistEmbeddingsRequest,
  runDiagnostics as runDiagnosticsRequest,
  runEvaluation as runEvaluationRequest,
  runQuery as runQueryRequest,
} from "./api";
import { presetQuestions, views } from "./constants";
import { formatBytes, formatTimestamp } from "./format";
import type {
  DiagnosticsResponse,
  DocumentItem,
  DocumentPreview,
  EvalCaseFilter,
  EvalDatasetInfo,
  EvalReportResponse,
  PersistedChunkDocument,
  PersistedEmbeddingDocument,
  QueryResponse,
  ViewKey,
} from "./types";

function App() {
  const [activeView, setActiveView] = useState<ViewKey>("documents");

  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedFilename, setSelectedFilename] = useState("");
  const [preview, setPreview] = useState<DocumentPreview | null>(null);
  const [chunkArtifact, setChunkArtifact] = useState<PersistedChunkDocument | null>(null);
  const [embeddingArtifact, setEmbeddingArtifact] = useState<PersistedEmbeddingDocument | null>(null);
  const [documentsError, setDocumentsError] = useState("");
  const [documentsBusy, setDocumentsBusy] = useState(false);
  const [artifactBusy, setArtifactBusy] = useState(false);
  const [artifactMessage, setArtifactMessage] = useState("");

  const [queryFilename, setQueryFilename] = useState("");
  const [question, setQuestion] = useState("What is RAG?");
  const [topK, setTopK] = useState(3);
  const [queryResult, setQueryResult] = useState<QueryResponse | null>(null);
  const [diagnosticsResult, setDiagnosticsResult] = useState<DiagnosticsResponse | null>(null);
  const [queryError, setQueryError] = useState("");
  const [queryBusy, setQueryBusy] = useState(false);

  const [datasets, setDatasets] = useState<EvalDatasetInfo[]>([]);
  const [datasetName, setDatasetName] = useState("");
  const [evalTopK, setEvalTopK] = useState(3);
  const [evalResult, setEvalResult] = useState<EvalReportResponse | null>(null);
  const [evalError, setEvalError] = useState("");
  const [evalBusy, setEvalBusy] = useState(false);
  const [evalCaseFilter, setEvalCaseFilter] = useState<EvalCaseFilter>("all");

  const activePresetQuestions =
    presetQuestions[queryFilename] ?? [
      "What is the main topic of this document?",
      "What are the most important system behaviors described here?",
    ];

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

  useEffect(() => {
    void loadDocuments();
    void loadDatasets();
  }, []);

  useEffect(() => {
    if (!selectedFilename && documents.length > 0) {
      setSelectedFilename(documents[0].filename);
      setQueryFilename(documents[0].filename);
    }
  }, [documents, selectedFilename]);

  useEffect(() => {
    if (!selectedFilename) {
      return;
    }

    void loadPreview(selectedFilename);
    void loadArtifactStatus(selectedFilename);
  }, [selectedFilename]);

  async function loadDocuments() {
    setDocumentsBusy(true);
    setDocumentsError("");

    try {
      const payload = await fetchDocuments();
      setDocuments(payload.documents);

      if (payload.documents.length > 0) {
        setSelectedFilename((current) => current || payload.documents[0].filename);
        setQueryFilename((current) => current || payload.documents[0].filename);
      }
    } catch (error) {
      setDocumentsError(error instanceof Error ? error.message : "Failed to load documents");
    } finally {
      setDocumentsBusy(false);
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

  async function loadDatasets() {
    try {
      const payload = await fetchEvaluationDatasets();
      setDatasets(payload.datasets);
      if (payload.datasets.length > 0) {
        setDatasetName((current) => current || payload.datasets[0].dataset_name);
      }
    } catch (error) {
      setEvalError(error instanceof Error ? error.message : "Failed to load evaluation datasets");
    }
  }

  async function submitQuery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setQueryBusy(true);
    setQueryError("");
    setQueryResult(null);

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

  async function submitEvaluation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setEvalBusy(true);
    setEvalError("");
    setEvalResult(null);

    try {
      const payload = await runEvaluationRequest(datasetName, evalTopK);
      setEvalResult(payload);
    } catch (error) {
      setEvalError(error instanceof Error ? error.message : "Failed to run evaluation");
    } finally {
      setEvalBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Enterprise RAG Agent Console</p>
          <h1>Agent Knowledge System</h1>
          <p className="hero-copy">
            A focused console for inspecting ingestion artifacts, tracing retrieval,
            and benchmarking retrieval quality across curated datasets.
          </p>
        </div>
        <div className="hero-stats">
          <div className="stat-card">
            <span>Documents</span>
            <strong>{documents.length}</strong>
          </div>
          <div className="stat-card">
            <span>Eval Datasets</span>
            <strong>{datasets.length}</strong>
          </div>
          <div className="stat-card">
            <span>Default Query Top-K</span>
            <strong>{topK}</strong>
          </div>
        </div>
      </header>

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

      {activeView === "documents" && (
        <section className="panel-grid">
          <article className="panel">
            <div className="panel-heading">
              <h2>Document Registry</h2>
              <button type="button" className="ghost-button" onClick={() => void loadDocuments()}>
                Refresh
              </button>
            </div>
            {documentsBusy && <p className="status">Loading documents...</p>}
            {documentsError && <p className="error">{documentsError}</p>}
            <div className="document-list">
              {documents.map((item) => (
                <button
                  key={item.filename}
                  type="button"
                  className={`document-card${selectedFilename === item.filename ? " active" : ""}`}
                  onClick={() => {
                    setSelectedFilename(item.filename);
                  }}
                >
                  <strong>{item.filename}</strong>
                  <span>{item.suffix}</span>
                  <small>{formatBytes(item.size_bytes)}</small>
                </button>
              ))}
            </div>
          </article>

          <article className="panel preview-panel">
            <div className="panel-heading">
              <h2>Document Pipeline</h2>
              <div className="button-row">
                {selectedFilename && (
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => void loadArtifactStatus(selectedFilename)}
                  >
                    Refresh Status
                  </button>
                )}
                <button type="button" className="secondary-button" onClick={() => void persistChunks()} disabled={artifactBusy || !selectedFilename}>
                  Persist Chunks
                </button>
                <button
                  type="button"
                  className="primary-button"
                  onClick={() => void persistEmbeddings()}
                  disabled={artifactBusy || !selectedFilename || !chunkArtifact}
                >
                  Persist Embeddings
                </button>
              </div>
            </div>
            {artifactBusy && <p className="status">Refreshing artifact status...</p>}
            {artifactMessage && <p className="status">{artifactMessage}</p>}
            <div className="artifact-grid">
              <article className="artifact-card">
                <header>
                  <strong>Chunk Artifact</strong>
                  <span>{chunkArtifact ? "ready" : "missing"}</span>
                </header>
                {chunkArtifact ? (
                  <>
                    <div className="meta-stack">
                      <span>Strategy: {chunkArtifact.chunk_strategy}</span>
                      <span>Chunks: {chunkArtifact.chunk_count}</span>
                      <span>Chunk Size: {chunkArtifact.chunk_size}</span>
                      <span>Overlap: {chunkArtifact.chunk_overlap}</span>
                      <span>Created: {formatTimestamp(chunkArtifact.created_at)}</span>
                    </div>
                  </>
                ) : (
                  <p className="muted">
                    No persisted chunk artifact yet. Generate paragraph chunks from the selected
                    document to enable downstream indexing.
                  </p>
                )}
              </article>
              <article className="artifact-card">
                <header>
                  <strong>Embedding Artifact</strong>
                  <span>{embeddingArtifact ? "ready" : "missing"}</span>
                </header>
                {embeddingArtifact ? (
                  <>
                    <div className="meta-stack">
                      <span>Provider: {embeddingArtifact.embedding_provider}</span>
                      <span>Model: {embeddingArtifact.embedding_model}</span>
                      <span>Dimension: {embeddingArtifact.vector_dim}</span>
                      <span>Chunks Indexed: {embeddingArtifact.chunk_count}</span>
                      <span>Created: {formatTimestamp(embeddingArtifact.created_at)}</span>
                    </div>
                  </>
                ) : (
                  <p className="muted">
                    No persisted embedding artifact yet. Embeddings can be generated after chunk
                    persistence succeeds.
                  </p>
                )}
              </article>
            </div>
            {preview ? (
              <>
                <div className="meta-row">
                  <span>{preview.filename}</span>
                  <span>{preview.suffix}</span>
                  <span>{formatBytes(preview.size_bytes)}</span>
                </div>
                <pre className="preview-text">{preview.content}</pre>
              </>
            ) : (
              <p className="muted">
                Select a document to inspect its content and current pipeline artifact status.
              </p>
            )}
          </article>
        </section>
      )}

      {activeView === "query" && (
        <section className="panel-grid query-layout">
          <article className="panel">
            <div className="panel-heading">
              <h2>Query Lab</h2>
              <button type="button" className="ghost-button" onClick={() => setDiagnosticsResult(null)}>
                Clear Diagnostics
              </button>
            </div>
            <form className="stack-form" onSubmit={submitQuery}>
              <label>
                Document
                <select value={queryFilename} onChange={(event) => setQueryFilename(event.target.value)}>
                  {documents.map((item) => (
                    <option key={item.filename} value={item.filename}>
                      {item.filename}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Question
                <textarea
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  rows={4}
                />
              </label>
              <div className="preset-strip">
                {activePresetQuestions.map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    className="preset-chip"
                    onClick={() => setQuestion(preset)}
                  >
                    {preset}
                  </button>
                ))}
              </div>
              <label>
                Top-K
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={topK}
                  onChange={(event) => setTopK(Number(event.target.value))}
                />
              </label>
              <div className="button-row">
                <button type="submit" className="primary-button" disabled={queryBusy}>
                  Run Query
                </button>
                <button type="button" className="secondary-button" disabled={queryBusy} onClick={() => void runDiagnostics()}>
                  Run Diagnostics
                </button>
              </div>
            </form>
            {queryBusy && <p className="status">Running retrieval pipeline...</p>}
            {queryError && <p className="error">{queryError}</p>}
          </article>

          <div className="query-results">
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
                <p className="muted">
                  Run a query to inspect answer text, provider selection, and top retrieved chunks.
                </p>
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
                <p className="muted">
                  Run diagnostics to inspect vector scores, rerank bonuses, and candidate ordering.
                </p>
              )}
            </article>
          </div>
        </section>
      )}

      {activeView === "evaluation" && (
        <section className="panel-grid">
          <article className="panel">
            <div className="panel-heading">
              <h2>Evaluation Runner</h2>
              <button type="button" className="ghost-button" onClick={() => void loadDatasets()}>
                Refresh Datasets
              </button>
            </div>
            <form className="stack-form" onSubmit={submitEvaluation}>
              <label>
                Dataset
                <select value={datasetName} onChange={(event) => setDatasetName(event.target.value)}>
                  {datasets.map((dataset) => (
                    <option key={dataset.dataset_name} value={dataset.dataset_name}>
                      {dataset.dataset_name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Top-K
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={evalTopK}
                  onChange={(event) => setEvalTopK(Number(event.target.value))}
                />
              </label>
              <button type="submit" className="primary-button" disabled={evalBusy}>
                Run Evaluation
              </button>
            </form>
            {evalBusy && <p className="status">Benchmarking retrieval set...</p>}
            {evalError && <p className="error">{evalError}</p>}
            <div className="dataset-list">
              {datasets.map((dataset) => (
                <article key={dataset.dataset_name} className="dataset-card">
                  <strong>{dataset.dataset_name}</strong>
                  <span>{dataset.case_count} cases</span>
                  <small>{dataset.filenames.join(", ")}</small>
                </article>
              ))}
            </div>
          </article>

          <article className="panel preview-panel">
            <div className="panel-heading">
              <h2>Evaluation Report</h2>
            </div>
            {evalResult ? (
              <>
                <div className="summary-strip">
                  <div className="summary-card">
                    <span className="trace-label">Total Cases</span>
                    <strong>{evalResult.report.summary.total_cases}</strong>
                  </div>
                  <div className="summary-card">
                    <span className="trace-label">Hit@{evalResult.report.top_k}</span>
                    <strong>{evalResult.report.summary.hit_rate_at_k.toFixed(3)}</strong>
                  </div>
                  <div className="summary-card">
                    <span className="trace-label">MRR</span>
                    <strong>{evalResult.report.summary.mean_reciprocal_rank.toFixed(3)}</strong>
                  </div>
                </div>
                <div className="panel-heading case-toolbar">
                  <h3>Case Results</h3>
                  <div className="filter-row">
                    <button
                      type="button"
                      className={`filter-chip${evalCaseFilter === "all" ? " active" : ""}`}
                      onClick={() => setEvalCaseFilter("all")}
                    >
                      All
                    </button>
                    <button
                      type="button"
                      className={`filter-chip${evalCaseFilter === "hit" ? " active" : ""}`}
                      onClick={() => setEvalCaseFilter("hit")}
                    >
                      Hits
                    </button>
                    <button
                      type="button"
                      className={`filter-chip${evalCaseFilter === "miss" ? " active" : ""}`}
                      onClick={() => setEvalCaseFilter("miss")}
                    >
                      Misses
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
                        <span>{item.hit_at_k ? "hit" : "miss"}</span>
                      </header>
                      <p>{item.question}</p>
                      <div className="meta-row">
                        <span>RR {item.reciprocal_rank.toFixed(3)}</span>
                        <span>file {item.filename}</span>
                      </div>
                      <small>Expected: {item.expected_chunk_ids.join(", ")}</small>
                      <small>Retrieved: {item.retrieved_chunk_ids.join(", ")}</small>
                    </article>
                  ))}
                </div>
                {filteredEvalCases.length === 0 && (
                  <p className="muted">
                    No cases match the current filter. Switch to another view to inspect all benchmark
                    cases again.
                  </p>
                )}
              </>
            ) : (
              <p className="muted">
                Select a dataset and run evaluation to view retrieval benchmark summaries and per-case outcomes.
              </p>
            )}
          </article>
        </section>
      )}
    </div>
  );
}

export default App;
