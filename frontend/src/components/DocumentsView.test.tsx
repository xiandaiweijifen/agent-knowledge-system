import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DocumentsView } from "./DocumentsView";

describe("DocumentsView", () => {
  const missingKnowledgeAssets = {
    chunks_ready: false,
    embeddings_ready: false,
    llamaindex_ready: false,
  };

  it("renders artifact readiness and triggers chunk persistence", async () => {
    const user = userEvent.setup();
    const onPersistChunks = vi.fn();
    const onUploadFile = vi.fn();
    const onGeneratePipeline = vi.fn();
    const onDeleteDocument = vi.fn();

    const view = render(
      <DocumentsView
        locale="en"
        documents={[
          {
            filename: "rag_overview.md",
            size_bytes: 1024,
            suffix: ".md",
            knowledge_assets: {
              chunks_ready: true,
              embeddings_ready: false,
              llamaindex_ready: false,
            },
          },
        ]}
        selectedFilename="rag_overview.md"
        preview={{
          filename: "rag_overview.md",
          suffix: ".md",
          size_bytes: 1024,
          content: "# RAG Overview",
        }}
        chunkArtifact={{
          filename: "rag_overview.md",
          suffix: ".md",
          source_path: "../data/raw/rag_overview.md",
          created_at: "2026-03-14T00:00:00+00:00",
          pipeline_version: "ingestion-v1",
          chunk_strategy: "paragraph",
          chunk_count: 8,
          chunk_size: 500,
          chunk_overlap: 100,
        }}
        embeddingArtifact={null}
        documentsBusy={false}
        artifactBusy={false}
        uploadBusy={false}
        documentsError=""
        artifactMessage=""
        uploadMessage=""
        onRefreshDocuments={vi.fn()}
        onSelectDocument={vi.fn()}
        onRefreshArtifacts={vi.fn()}
        onPersistChunks={onPersistChunks}
        onPersistEmbeddings={vi.fn()}
        onGeneratePipeline={onGeneratePipeline}
        onDeleteDocument={onDeleteDocument}
        onUploadFile={onUploadFile}
      />,
    );

    expect(screen.getByText("Chunk Artifact")).toBeInTheDocument();
    expect(screen.getByText("ready")).toBeInTheDocument();
    expect(screen.getByText("missing")).toBeInTheDocument();
    expect(screen.getByText("Strategy: paragraph")).toBeInTheDocument();
    expect(screen.getAllByText("chunks ready")).toHaveLength(2);
    expect(screen.getAllByText("embeddings missing")).toHaveLength(2);
    expect(screen.getByText("llamaindex missing")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Persist Chunks" }));
    expect(onPersistChunks).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Generate Pipeline" }));
    expect(onGeneratePipeline).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Delete Document" }));
    expect(onDeleteDocument).toHaveBeenCalledTimes(1);

    await user.upload(
      screen.getByLabelText("Upload Document"),
      new File(["hello"], "notes.md", { type: "text/markdown" }),
    );
    expect(onUploadFile).toHaveBeenCalledTimes(1);
  });

  it("limits the registry to 5 files by default and supports filename search", async () => {
    const user = userEvent.setup();
    const onSelectDocument = vi.fn();

    const view = render(
      <DocumentsView
        locale="en"
        documents={[
          { filename: "agent_workflow.md", size_bytes: 100, suffix: ".md", knowledge_assets: missingKnowledgeAssets },
          { filename: "checkout_service_runbook.md", size_bytes: 101, suffix: ".md", knowledge_assets: missingKnowledgeAssets },
          { filename: "customer_support_tickets_1.md", size_bytes: 102, suffix: ".md", knowledge_assets: missingKnowledgeAssets },
          { filename: "incident_playbook.md", size_bytes: 103, suffix: ".md", knowledge_assets: missingKnowledgeAssets },
          { filename: "it_support_v2_1.md", size_bytes: 104, suffix: ".md", knowledge_assets: missingKnowledgeAssets },
          { filename: "payment_service_runbook.md", size_bytes: 105, suffix: ".md", knowledge_assets: missingKnowledgeAssets },
        ]}
        selectedFilename="agent_workflow.md"
        preview={null}
        chunkArtifact={null}
        embeddingArtifact={null}
        documentsBusy={false}
        artifactBusy={false}
        uploadBusy={false}
        documentsError=""
        artifactMessage=""
        uploadMessage=""
        onRefreshDocuments={vi.fn()}
        onSelectDocument={onSelectDocument}
        onRefreshArtifacts={vi.fn()}
        onPersistChunks={vi.fn()}
        onPersistEmbeddings={vi.fn()}
        onGeneratePipeline={vi.fn()}
        onDeleteDocument={vi.fn()}
        onUploadFile={vi.fn()}
      />,
    );

    const registryPanel = screen.getAllByText("Document Registry").at(-1)?.closest("article");
    expect(registryPanel).toBeTruthy();
    const scoped = within(registryPanel!);

    expect(scoped.getByText("Showing 5 / 6")).toBeInTheDocument();
    expect(scoped.queryByText("payment_service_runbook.md")).not.toBeInTheDocument();

    await user.click(scoped.getByRole("button", { name: "Show All Files" }));
    expect(scoped.getByText("payment_service_runbook.md")).toBeInTheDocument();

    const searchInput = scoped.getByPlaceholderText("Search by filename");
    expect(searchInput).toBeDefined();
    await user.type(searchInput, "payment");
    expect(scoped.getByText("Showing 1 / 1")).toBeInTheDocument();
    expect(scoped.getByText("payment_service_runbook.md")).toBeInTheDocument();
    expect(scoped.queryByText("agent_workflow.md")).not.toBeInTheDocument();

    await user.click(scoped.getByText("payment_service_runbook.md").closest("button")!);
    expect(onSelectDocument).toHaveBeenCalledWith("payment_service_runbook.md");
  });
});
