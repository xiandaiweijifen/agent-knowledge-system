import { FormEvent, useEffect, useState } from "react";
import {
  deleteDocument as deleteDocumentRequest,
  fetchDocumentPreview,
  fetchDocuments,
  fetchEvaluationDatasets,
  fetchPersistedChunks,
  fetchPersistedEmbeddings,
  fetchSystemHealth,
  persistChunks as persistChunksRequest,
  persistEmbeddings as persistEmbeddingsRequest,
  runDiagnostics as runDiagnosticsRequest,
  runEvaluation as runEvaluationRequest,
  runQuery as runQueryRequest,
  uploadDocument as uploadDocumentRequest,
} from "./api";
import { DocumentsView } from "./components/DocumentsView";
import { EvaluationView } from "./components/EvaluationView";
import { QueryView } from "./components/QueryView";
import { presetQuestions, views } from "./constants";
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
  SystemHealthResponse,
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
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");
  const [systemHealth, setSystemHealth] = useState<SystemHealthResponse | null>(null);
  const [systemHealthError, setSystemHealthError] = useState("");

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
    void loadSystemHealth();
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

      const payload = await fetchDocuments();
      setDocuments(payload.documents);

      if (payload.documents.length > 0) {
        setSelectedFilename(payload.documents[0].filename);
        setQueryFilename(payload.documents[0].filename);
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
      setQueryFilename(payload.filename);
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

      <section className="status-banner">
        <div className="status-pill">
          <span>Backend</span>
          <strong>{systemHealth?.status ?? "unknown"}</strong>
        </div>
        <div className="status-pill">
          <span>Environment</span>
          <strong>{systemHealth?.app_env ?? "unavailable"}</strong>
        </div>
        <div className="status-pill">
          <span>Embedding</span>
          <strong>
            {systemHealth
              ? `${systemHealth.embedding_provider} / ${systemHealth.embedding_model}`
              : "unavailable"}
          </strong>
        </div>
        <div className="status-pill">
          <span>Chat</span>
          <strong>
            {systemHealth ? `${systemHealth.chat_provider} / ${systemHealth.chat_model}` : "unavailable"}
          </strong>
        </div>
        <div className="status-pill">
          <span>Provider Keys</span>
          <strong>
            {systemHealth
              ? `Gemini ${systemHealth.providers.gemini_configured ? "on" : "off"} · OpenAI ${
                  systemHealth.providers.openai_configured ? "on" : "off"
                }`
              : "unavailable"}
          </strong>
        </div>
        <div className="status-pill">
          <span>Infra</span>
          <strong>
            {systemHealth
              ? `DB ${systemHealth.storage.database_configured ? "on" : "off"} · Redis ${
                  systemHealth.storage.redis_configured ? "on" : "off"
                }`
              : "unavailable"}
          </strong>
        </div>
      </section>
      {systemHealthError && <p className="error">{systemHealthError}</p>}

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
        <DocumentsView
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
          onSelectDocument={setSelectedFilename}
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
          documents={documents}
          queryFilename={queryFilename}
          question={question}
          topK={topK}
          activePresetQuestions={activePresetQuestions}
          queryResult={queryResult}
          diagnosticsResult={diagnosticsResult}
          queryError={queryError}
          queryBusy={queryBusy}
          onChangeDocument={setQueryFilename}
          onChangeQuestion={setQuestion}
          onChangeTopK={setTopK}
          onClearDiagnostics={() => setDiagnosticsResult(null)}
          onSubmitQuery={submitQuery}
          onRunDiagnostics={() => void runDiagnostics()}
        />
      )}

      {activeView === "evaluation" && (
        <EvaluationView
          datasets={datasets}
          datasetName={datasetName}
          evalTopK={evalTopK}
          evalResult={evalResult}
          evalError={evalError}
          evalBusy={evalBusy}
          evalCaseFilter={evalCaseFilter}
          filteredEvalCases={filteredEvalCases}
          onRefreshDatasets={() => void loadDatasets()}
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
