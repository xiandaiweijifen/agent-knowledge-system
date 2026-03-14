import type { ChangeEvent } from "react";

import { formatBytes, formatTimestamp } from "../format";
import type {
  DocumentItem,
  DocumentPreview,
  PersistedChunkDocument,
  PersistedEmbeddingDocument,
} from "../types";

type DocumentsViewProps = {
  documents: DocumentItem[];
  selectedFilename: string;
  preview: DocumentPreview | null;
  chunkArtifact: PersistedChunkDocument | null;
  embeddingArtifact: PersistedEmbeddingDocument | null;
  documentsBusy: boolean;
  artifactBusy: boolean;
  uploadBusy: boolean;
  documentsError: string;
  artifactMessage: string;
  uploadMessage: string;
  onRefreshDocuments: () => void;
  onSelectDocument: (filename: string) => void;
  onRefreshArtifacts: () => void;
  onPersistChunks: () => void;
  onPersistEmbeddings: () => void;
  onGeneratePipeline: () => void;
  onDeleteDocument: () => void;
  onUploadFile: (event: ChangeEvent<HTMLInputElement>) => void;
};

export function DocumentsView({
  documents,
  selectedFilename,
  preview,
  chunkArtifact,
  embeddingArtifact,
  documentsBusy,
  artifactBusy,
  uploadBusy,
  documentsError,
  artifactMessage,
  uploadMessage,
  onRefreshDocuments,
  onSelectDocument,
  onRefreshArtifacts,
  onPersistChunks,
  onPersistEmbeddings,
  onGeneratePipeline,
  onDeleteDocument,
  onUploadFile,
}: DocumentsViewProps) {
  return (
    <section className="panel-grid">
      <article className="panel">
        <div className="panel-heading">
          <h2>Document Registry</h2>
          <button type="button" className="ghost-button" onClick={onRefreshDocuments}>
            Refresh
          </button>
        </div>
        <label className="upload-dropzone">
          <span className="section-label">Upload Document</span>
          <strong>Add a .txt or .md file</strong>
          <small>The backend will persist it under the raw document store.</small>
          <input
            type="file"
            accept=".txt,.md,text/plain,text/markdown"
            aria-label="Upload Document"
            onChange={onUploadFile}
            disabled={uploadBusy}
          />
        </label>
        {uploadBusy && <p className="status">Uploading document...</p>}
        {uploadMessage && <p className="status">{uploadMessage}</p>}
        {documentsBusy && <p className="status">Loading documents...</p>}
        {documentsError && <p className="error">{documentsError}</p>}
        <div className="document-list">
          {documents.map((item) => (
            <button
              key={item.filename}
              type="button"
              className={`document-card${selectedFilename === item.filename ? " active" : ""}`}
              onClick={() => onSelectDocument(item.filename)}
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
              <button type="button" className="ghost-button" onClick={onRefreshArtifacts}>
                Refresh Status
              </button>
            )}
            <button
              type="button"
              className="secondary-button"
              onClick={onPersistChunks}
              disabled={artifactBusy || !selectedFilename}
            >
              Persist Chunks
            </button>
            <button
              type="button"
              className="primary-button"
              onClick={onPersistEmbeddings}
              disabled={artifactBusy || !selectedFilename || !chunkArtifact}
            >
              Persist Embeddings
            </button>
            <button
              type="button"
              className="primary-button"
              onClick={onGeneratePipeline}
              disabled={artifactBusy || !selectedFilename}
            >
              Generate Pipeline
            </button>
            <button
              type="button"
              className="danger-button"
              onClick={onDeleteDocument}
              disabled={artifactBusy || uploadBusy || !selectedFilename}
            >
              Delete Document
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
              <div className="meta-stack">
                <span>Strategy: {chunkArtifact.chunk_strategy}</span>
                <span>Chunks: {chunkArtifact.chunk_count}</span>
                <span>Chunk Size: {chunkArtifact.chunk_size}</span>
                <span>Overlap: {chunkArtifact.chunk_overlap}</span>
                <span>Created: {formatTimestamp(chunkArtifact.created_at)}</span>
              </div>
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
              <div className="meta-stack">
                <span>Provider: {embeddingArtifact.embedding_provider}</span>
                <span>Model: {embeddingArtifact.embedding_model}</span>
                <span>Dimension: {embeddingArtifact.vector_dim}</span>
                <span>Chunks Indexed: {embeddingArtifact.chunk_count}</span>
                <span>Created: {formatTimestamp(embeddingArtifact.created_at)}</span>
              </div>
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
  );
}
