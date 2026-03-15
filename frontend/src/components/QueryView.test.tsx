import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { QueryView } from "./QueryView";

describe("QueryView", () => {
  it("applies a preset question and renders query trace", async () => {
    const user = userEvent.setup();
    const onChangeQuestion = vi.fn();

    render(
      <QueryView
        documents={[
          {
            filename: "rag_overview.md",
            size_bytes: 1024,
            suffix: ".md",
          },
        ]}
        queryFilename="rag_overview.md"
        question="What is RAG?"
        topK={3}
        activePresetQuestions={[
          "What is RAG?",
          "Why is chunking important in a RAG system?",
        ]}
        queryResult={{
          filename: "rag_overview.md",
          question: "What is RAG?",
          answer: "RAG combines retrieval with generation.",
          answer_source: "gemini",
          model: "gemini-2.5-flash-lite",
          answered_at: "2026-03-14T00:00:00+00:00",
          answer_latency_ms: 12.5,
          chat_provider: "gemini",
          chat_model: "gemini-2.5-flash-lite",
          retrieval: {
            filename: "rag_overview.md",
            embedding_provider: "gemini",
            embedding_model: "gemini-embedding-001",
            vector_dim: 3072,
            question: "What is RAG?",
            top_k: 3,
            retrieved_at: "2026-03-14T00:00:00+00:00",
            retrieval_latency_ms: 8.2,
            query_embedding_provider: "gemini",
            query_embedding_model: "gemini-embedding-001",
            matches: [
              {
                chunk_id: "rag_overview.md::chunk_0",
                chunk_index: 0,
                source_filename: "rag_overview.md",
                source_suffix: ".md",
                char_count: 400,
                content: "Retrieval-augmented generation, or RAG, is ...",
                score: 0.95,
                vector_score: 0.66,
                rerank_bonus: 0.29,
              },
            ],
          },
        }}
        agentQueryResult={{
          question: "What is RAG?",
          workflow_status: "completed",
          route: {
            route_type: "knowledge_retrieval",
            route_reason: "Question is a knowledge lookup.",
            filename: "rag_overview.md",
          },
          workflow_trace: [
            {
              stage: "routing",
              status: "completed",
              timestamp: "2026-03-14T00:00:00+00:00",
              detail: "Route selected knowledge retrieval.",
            },
          ],
          filename: "rag_overview.md",
          answer: "RAG combines retrieval with generation.",
          answer_source: "gemini",
          model: "gemini-2.5-flash-lite",
          answered_at: "2026-03-14T00:00:00+00:00",
          answer_latency_ms: 12.5,
          chat_provider: "gemini",
          chat_model: "gemini-2.5-flash-lite",
          retrieval: {
            filename: "rag_overview.md",
            embedding_provider: "gemini",
            embedding_model: "gemini-embedding-001",
            vector_dim: 3072,
            question: "What is RAG?",
            top_k: 3,
            retrieved_at: "2026-03-14T00:00:00+00:00",
            retrieval_latency_ms: 8.2,
            query_embedding_provider: "gemini",
            query_embedding_model: "gemini-embedding-001",
            matches: [],
          },
          tool_chain: [],
          tool_execution: {
            tool_name: "ticketing",
            action: "create",
            target: "payment-service",
            execution_status: "completed",
            execution_mode: "local_adapter",
            result_summary: "Created local ticket TICKET-0001 for payment-service.",
            trace_id: "trace-1",
            executed_at: "2026-03-14T00:00:00+00:00",
            output: {
              ticket_id: "TICKET-0001",
              status: "open",
              severity: "high",
              environment: "production",
            },
          },
        }}
        diagnosticsResult={null}
        queryError=""
        queryBusy={false}
        onChangeDocument={vi.fn()}
        onChangeQuestion={onChangeQuestion}
        onChangeTopK={vi.fn()}
        onClearDiagnostics={vi.fn()}
        onSubmitQuery={(event) => event.preventDefault()}
        onRunAgent={vi.fn()}
        onRunDiagnostics={vi.fn()}
      />,
    );

    expect(screen.getByText("Answer Trace")).toBeInTheDocument();
    expect(screen.getByText("Agent Workflow")).toBeInTheDocument();
    expect(screen.getByText("knowledge_retrieval")).toBeInTheDocument();
    expect(screen.getAllByText("RAG combines retrieval with generation.")).toHaveLength(2);
    expect(screen.getByText("gemini-2.5-flash-lite")).toBeInTheDocument();
    expect(screen.getByText("Tool Output")).toBeInTheDocument();
    expect(screen.getByText("Ticket Id")).toBeInTheDocument();
    expect(screen.getAllByText("TICKET-0001").length).toBeGreaterThan(0);
    expect(screen.getAllByText("open").length).toBeGreaterThan(0);

    await user.click(
      screen.getByRole("button", { name: "Why is chunking important in a RAG system?" }),
    );

    expect(onChangeQuestion).toHaveBeenCalledWith(
      "Why is chunking important in a RAG system?",
    );
  });

  it("renders ticket list execution details for ticketing list workflows", () => {
    render(
      <QueryView
        documents={[
          {
            filename: "rag_overview.md",
            size_bytes: 1024,
            suffix: ".md",
          },
        ]}
        queryFilename="rag_overview.md"
        question="List open tickets"
        topK={3}
        activePresetQuestions={["List open tickets"]}
        queryResult={null}
        agentQueryResult={{
          question: "List open tickets",
          workflow_status: "completed",
          route: {
            route_type: "tool_execution",
            route_reason: "Ticket list requests should go through tool execution.",
            filename: "rag_overview.md",
          },
          workflow_trace: [
            {
              stage: "routing",
              status: "completed",
              timestamp: "2026-03-14T00:00:00+00:00",
              detail: "Route selected tool execution.",
            },
          ],
          tool_chain: [
            {
              question: "List open tickets",
              tool_plan: {
                question: "List open tickets",
                planning_mode: "heuristic_stub",
                route_hint: "tool_execution",
                tool_name: "ticketing",
                action: "list",
                target: "tickets",
                arguments: { status: "open" },
                plan_summary: "Plan ticketing:list for tickets using a local heuristic planner.",
              },
              tool_execution: {
                tool_name: "ticketing",
                action: "list",
                target: "tickets",
                execution_status: "completed",
                execution_mode: "local_adapter",
                result_summary: "Loaded 2 local ticket(s).",
                trace_id: "trace-step-1",
                executed_at: "2026-03-14T00:00:00+00:00",
                output: {
                  ticket_count: "2",
                  status_filter: "open",
                  tickets: "TICKET-0001 [open] payment-service | TICKET-0002 [open] checkout-api",
                },
              },
            },
          ],
          tool_plan: {
            question: "List open tickets",
            planning_mode: "heuristic_stub",
            route_hint: "tool_execution",
            tool_name: "ticketing",
            action: "list",
            target: "tickets",
            arguments: { status: "open" },
            plan_summary: "Plan ticketing:list for tickets using a local heuristic planner.",
          },
          tool_execution: {
            tool_name: "ticketing",
            action: "list",
            target: "tickets",
            execution_status: "completed",
            execution_mode: "local_adapter",
            result_summary: "Loaded 2 local ticket(s).",
            trace_id: "trace-2",
            executed_at: "2026-03-14T00:00:00+00:00",
            output: {
              ticket_count: "2",
              status_filter: "open",
              tickets: "TICKET-0001 [open] payment-service | TICKET-0002 [open] checkout-api",
            },
          },
        }}
        diagnosticsResult={null}
        queryError=""
        queryBusy={false}
        onChangeDocument={vi.fn()}
        onChangeQuestion={vi.fn()}
        onChangeTopK={vi.fn()}
        onClearDiagnostics={vi.fn()}
        onSubmitQuery={(event) => event.preventDefault()}
        onRunAgent={vi.fn()}
        onRunDiagnostics={vi.fn()}
      />,
    );

    expect(screen.getByText("Ticket Count")).toBeInTheDocument();
    expect(screen.getByText("Status Filter")).toBeInTheDocument();
    expect(screen.getByText("Executed Steps")).toBeInTheDocument();
    expect(screen.getByText("Final Step")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("TICKET-0001 [open] payment-service")).toBeInTheDocument();
    expect(screen.getByText("TICKET-0002 [open] checkout-api")).toBeInTheDocument();
    expect(screen.queryByText("Ticket Id")).not.toBeInTheDocument();
  });
});
