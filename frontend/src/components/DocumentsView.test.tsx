import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DocumentsView } from "./DocumentsView";

describe("DocumentsView", () => {
  it("renders artifact readiness and triggers chunk persistence", async () => {
    const user = userEvent.setup();
    const onPersistChunks = vi.fn();

    render(
      <DocumentsView
        documents={[
          {
            filename: "rag_overview.md",
            size_bytes: 1024,
            suffix: ".md",
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
        documentsError=""
        artifactMessage=""
        onRefreshDocuments={vi.fn()}
        onSelectDocument={vi.fn()}
        onRefreshArtifacts={vi.fn()}
        onPersistChunks={onPersistChunks}
        onPersistEmbeddings={vi.fn()}
      />,
    );

    expect(screen.getByText("Chunk Artifact")).toBeInTheDocument();
    expect(screen.getByText("ready")).toBeInTheDocument();
    expect(screen.getByText("missing")).toBeInTheDocument();
    expect(screen.getByText("Strategy: paragraph")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Persist Chunks" }));
    expect(onPersistChunks).toHaveBeenCalledTimes(1);
  });
});
