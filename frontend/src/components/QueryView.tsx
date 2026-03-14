import type { FormEvent } from "react";

import type { DiagnosticsResponse, DocumentItem, QueryResponse } from "../types";

type QueryViewProps = {
  documents: DocumentItem[];
  queryFilename: string;
  question: string;
  topK: number;
  activePresetQuestions: string[];
  queryResult: QueryResponse | null;
  diagnosticsResult: DiagnosticsResponse | null;
  queryError: string;
  queryBusy: boolean;
  onChangeDocument: (filename: string) => void;
  onChangeQuestion: (question: string) => void;
  onChangeTopK: (value: number) => void;
  onClearDiagnostics: () => void;
  onSubmitQuery: (event: FormEvent<HTMLFormElement>) => void;
  onRunDiagnostics: () => void;
};

export function QueryView({
  documents,
  queryFilename,
  question,
  topK,
  activePresetQuestions,
  queryResult,
  diagnosticsResult,
  queryError,
  queryBusy,
  onChangeDocument,
  onChangeQuestion,
  onChangeTopK,
  onClearDiagnostics,
  onSubmitQuery,
  onRunDiagnostics,
}: QueryViewProps) {
  return (
    <section className="panel-grid query-layout">
      <article className="panel">
        <div className="panel-heading">
          <h2>Query Lab</h2>
          <button type="button" className="ghost-button" onClick={onClearDiagnostics}>
            Clear Diagnostics
          </button>
        </div>
        <form className="stack-form" onSubmit={onSubmitQuery}>
          <label>
            Document
            <select value={queryFilename} onChange={(event) => onChangeDocument(event.target.value)}>
              {documents.map((item) => (
                <option key={item.filename} value={item.filename}>
                  {item.filename}
                </option>
              ))}
            </select>
          </label>
          <label>
            Question
            <textarea value={question} onChange={(event) => onChangeQuestion(event.target.value)} rows={4} />
          </label>
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
            <button type="submit" className="primary-button" disabled={queryBusy}>
              Run Query
            </button>
            <button type="button" className="secondary-button" disabled={queryBusy} onClick={onRunDiagnostics}>
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
  );
}
