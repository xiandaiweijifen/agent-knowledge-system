import type { ChangeEvent } from "react";

import { formatBytes, formatTimestamp } from "../format";
import type {
  DocumentItem,
  DocumentPreview,
  Locale,
  PersistedChunkDocument,
  PersistedEmbeddingDocument,
} from "../types";

type DocumentsViewProps = {
  locale: Locale;
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
  locale,
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
  const copy =
    locale === "zh"
      ? {
          workspace: "文档工作台",
          title: "摄取与产物控制",
          banner: "上传源文件、检查持久化产物，并将文档推进到可检索流水线中。",
          noSelection: "未选择",
          docs: "份文档",
          chunksReady: "chunks 已就绪",
          chunksMissing: "chunks 缺失",
          embeddingsReady: "embeddings 已就绪",
          embeddingsMissing: "embeddings 缺失",
          registry: "文档注册表",
          registryCopy: "在文档进入切块和 embedding 之前管理原始知识文件。",
          refresh: "刷新",
          upload: "上传文档",
          uploadHint: "添加一个 .txt 或 .md 文件",
          uploadCopy: "后端会将它保存到原始文档存储中。",
          uploading: "正在上传文档...",
          loading: "正在加载文档...",
          noDocuments: "暂无文档",
          noDocumentsCopy: "上传 markdown 或文本文件以启动摄取流水线。",
          pipeline: "文档流水线",
          pipelineCopy: "检查持久化产物，并将选中文档推进到可检索状态。",
          refreshStatus: "刷新状态",
          persistChunks: "持久化 Chunks",
          persistEmbeddings: "持久化 Embeddings",
          generatePipeline: "生成流水线",
          deleteDocument: "删除文档",
          refreshingArtifacts: "正在刷新产物状态...",
          chunkArtifact: "Chunk 产物",
          embeddingArtifact: "Embedding 产物",
          ready: "已就绪",
          missing: "缺失",
          strategy: "策略",
          chunks: "Chunks",
          chunkSize: "Chunk 大小",
          overlap: "重叠",
          created: "创建时间",
          noChunkArtifact:
            "当前还没有持久化 chunk 产物。先为文档生成段落 chunks，再进行下游索引。",
          provider: "提供方",
          model: "模型",
          dimension: "维度",
          chunksIndexed: "已索引 Chunks",
          noEmbeddingArtifact:
            "当前还没有持久化 embedding 产物。chunk 持久化成功后再生成 embedding。",
          noDocumentSelected: "未选择文档",
          noDocumentSelectedCopy: "选择一个文档以查看内容和当前流水线产物状态。",
        }
      : {
          workspace: "Documents Workspace",
          title: "Ingestion And Artifact Control",
          banner:
            "Upload source files, inspect persisted artifacts, and promote a document into the retrieval pipeline.",
          noSelection: "no selection",
          docs: "docs",
          chunksReady: "chunks ready",
          chunksMissing: "chunks missing",
          embeddingsReady: "embeddings ready",
          embeddingsMissing: "embeddings missing",
          registry: "Document Registry",
          registryCopy: "Manage raw knowledge files before they enter chunking and embedding.",
          refresh: "Refresh",
          upload: "Upload Document",
          uploadHint: "Add a .txt or .md file",
          uploadCopy: "The backend will persist it under the raw document store.",
          uploading: "Uploading document...",
          loading: "Loading documents...",
          noDocuments: "No documents yet",
          noDocumentsCopy: "Upload a markdown or text file to start the ingestion pipeline.",
          pipeline: "Document Pipeline",
          pipelineCopy:
            "Inspect persisted artifacts and move the selected document into a retrievable state.",
          refreshStatus: "Refresh Status",
          persistChunks: "Persist Chunks",
          persistEmbeddings: "Persist Embeddings",
          generatePipeline: "Generate Pipeline",
          deleteDocument: "Delete Document",
          refreshingArtifacts: "Refreshing artifact status...",
          chunkArtifact: "Chunk Artifact",
          embeddingArtifact: "Embedding Artifact",
          ready: "ready",
          missing: "missing",
          strategy: "Strategy",
          chunks: "Chunks",
          chunkSize: "Chunk Size",
          overlap: "Overlap",
          created: "Created",
          noChunkArtifact:
            "No persisted chunk artifact yet. Generate paragraph chunks from the selected document to enable downstream indexing.",
          provider: "Provider",
          model: "Model",
          dimension: "Dimension",
          chunksIndexed: "Chunks Indexed",
          noEmbeddingArtifact:
            "No persisted embedding artifact yet. Embeddings can be generated after chunk persistence succeeds.",
          noDocumentSelected: "No document selected",
          noDocumentSelectedCopy:
            "Select a document to inspect its content and current pipeline artifact status.",
        };

  return (
    <section className="panel-grid">
      <article className="panel panel-span view-banner">
        <div className="view-banner-content">
          <div>
            <span className="section-label">{copy.workspace}</span>
            <h2 className="view-banner-title">{copy.title}</h2>
            <p className="view-banner-copy">{copy.banner}</p>
          </div>
          <div className="view-banner-meta">
            <span>{documents.length} {copy.docs}</span>
            <span>{selectedFilename || copy.noSelection}</span>
            <span>{chunkArtifact ? copy.chunksReady : copy.chunksMissing}</span>
            <span>{embeddingArtifact ? copy.embeddingsReady : copy.embeddingsMissing}</span>
          </div>
        </div>
      </article>

      <article className="panel">
        <div className="panel-heading">
          <div>
            <h2>{copy.registry}</h2>
            <p className="panel-intro">{copy.registryCopy}</p>
          </div>
          <button type="button" className="ghost-button" onClick={onRefreshDocuments}>
            {copy.refresh}
          </button>
        </div>
        <label className="upload-dropzone">
          <span className="section-label">{copy.upload}</span>
          <strong>{copy.uploadHint}</strong>
          <small>{copy.uploadCopy}</small>
          <input
            type="file"
            accept=".txt,.md,text/plain,text/markdown"
            aria-label="Upload Document"
            onChange={onUploadFile}
            disabled={uploadBusy}
          />
        </label>
        {uploadBusy && <p className="status">{copy.uploading}</p>}
        {uploadMessage && <p className="status">{uploadMessage}</p>}
        {documentsBusy && <p className="status">{copy.loading}</p>}
        {documentsError && <p className="error">{documentsError}</p>}
        {documents.length > 0 ? (
          <div className="document-list">
            {documents.map((item) => (
              <button
                key={item.filename}
                type="button"
                className={`document-card${selectedFilename === item.filename ? " active" : ""}`}
                onClick={() => onSelectDocument(item.filename)}
              >
                <div className="card-title-row">
                  <strong>{item.filename}</strong>
                  <span className="file-pill">{item.suffix}</span>
                </div>
                <small>{formatBytes(item.size_bytes)}</small>
              </button>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <strong>{copy.noDocuments}</strong>
            <p>{copy.noDocumentsCopy}</p>
          </div>
        )}
      </article>

      <article className="panel preview-panel">
        <div className="panel-heading">
          <div>
            <h2>{copy.pipeline}</h2>
            <p className="panel-intro">{copy.pipelineCopy}</p>
          </div>
        </div>
        <div className="button-row button-row-split">
          <div className="button-cluster">
            {selectedFilename && (
              <button type="button" className="ghost-button" onClick={onRefreshArtifacts}>
                {copy.refreshStatus}
              </button>
            )}
            <button
              type="button"
              className="secondary-button"
              onClick={onPersistChunks}
              disabled={artifactBusy || !selectedFilename}
            >
              {copy.persistChunks}
            </button>
            <button
              type="button"
              className="primary-button"
              onClick={onPersistEmbeddings}
              disabled={artifactBusy || !selectedFilename || !chunkArtifact}
            >
              {copy.persistEmbeddings}
            </button>
            <button
              type="button"
              className="primary-button"
              onClick={onGeneratePipeline}
              disabled={artifactBusy || !selectedFilename}
            >
              {copy.generatePipeline}
            </button>
          </div>
          <div className="button-cluster button-cluster-danger">
            <button
              type="button"
              className="danger-button"
              onClick={onDeleteDocument}
              disabled={artifactBusy || uploadBusy || !selectedFilename}
            >
              {copy.deleteDocument}
            </button>
          </div>
        </div>
        {artifactBusy && <p className="status">{copy.refreshingArtifacts}</p>}
        {artifactMessage && <p className="status">{artifactMessage}</p>}
        <div className="artifact-grid">
          <article className="artifact-card">
            <header>
              <strong>{copy.chunkArtifact}</strong>
              <span className={`status-chip${chunkArtifact ? " success" : ""}`}>
                {chunkArtifact ? copy.ready : copy.missing}
              </span>
            </header>
            {chunkArtifact ? (
              <div className="meta-stack">
                <span>{copy.strategy}: {chunkArtifact.chunk_strategy}</span>
                <span>{copy.chunks}: {chunkArtifact.chunk_count}</span>
                <span>{copy.chunkSize}: {chunkArtifact.chunk_size}</span>
                <span>{copy.overlap}: {chunkArtifact.chunk_overlap}</span>
                <span>{copy.created}: {formatTimestamp(chunkArtifact.created_at)}</span>
              </div>
            ) : (
              <p className="muted">{copy.noChunkArtifact}</p>
            )}
          </article>
          <article className="artifact-card">
            <header>
              <strong>{copy.embeddingArtifact}</strong>
              <span className={`status-chip${embeddingArtifact ? " success" : ""}`}>
                {embeddingArtifact ? copy.ready : copy.missing}
              </span>
            </header>
            {embeddingArtifact ? (
              <div className="meta-stack">
                <span>{copy.provider}: {embeddingArtifact.embedding_provider}</span>
                <span>{copy.model}: {embeddingArtifact.embedding_model}</span>
                <span>{copy.dimension}: {embeddingArtifact.vector_dim}</span>
                <span>{copy.chunksIndexed}: {embeddingArtifact.chunk_count}</span>
                <span>{copy.created}: {formatTimestamp(embeddingArtifact.created_at)}</span>
              </div>
            ) : (
              <p className="muted">{copy.noEmbeddingArtifact}</p>
            )}
          </article>
        </div>
        {preview ? (
          <>
            <div className="meta-row preview-meta">
              <span>{preview.filename}</span>
              <span>{preview.suffix}</span>
              <span>{formatBytes(preview.size_bytes)}</span>
            </div>
            <pre className="preview-text">{preview.content}</pre>
          </>
        ) : (
          <div className="empty-state empty-state-large">
            <strong>{copy.noDocumentSelected}</strong>
            <p>{copy.noDocumentSelectedCopy}</p>
          </div>
        )}
      </article>
    </section>
  );
}
