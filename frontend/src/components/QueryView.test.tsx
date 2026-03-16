import { render, screen, within } from "@testing-library/react";
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
        agentWorkflowRuns={[]}
        diagnosticsResult={null}
        queryError=""
        queryBusy={false}
        onChangeDocument={vi.fn()}
        onChangeQuestion={onChangeQuestion}
        onChangeTopK={vi.fn()}
        onClearDiagnostics={vi.fn()}
        onSubmitQuery={(event) => event.preventDefault()}
        onRunAgent={vi.fn()}
        onLoadAgentWorkflowRun={vi.fn()}
        onRecoverAgentWorkflowRun={vi.fn()}
        onRunDiagnostics={vi.fn()}
      />,
    );

    expect(screen.getByText("Answer Trace")).toBeInTheDocument();
    expect(screen.getByText("Agent Workflow")).toBeInTheDocument();
    expect(
      screen.getByText((content) => content.includes("Run Agent") && content.includes("without one")),
    ).toBeInTheDocument();
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
              step_id: "step_1",
              step_index: 1,
              step_status: "completed",
              attempt_count: 1,
              retried: false,
              started_at: "2026-03-14T00:00:00+00:00",
              completed_at: "2026-03-14T00:00:00+00:00",
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
        agentWorkflowRuns={[]}
        diagnosticsResult={null}
        queryError=""
        queryBusy={false}
        onChangeDocument={vi.fn()}
        onChangeQuestion={vi.fn()}
        onChangeTopK={vi.fn()}
        onClearDiagnostics={vi.fn()}
        onSubmitQuery={(event) => event.preventDefault()}
        onRunAgent={vi.fn()}
        onLoadAgentWorkflowRun={vi.fn()}
        onRecoverAgentWorkflowRun={vi.fn()}
        onRunDiagnostics={vi.fn()}
      />,
    );

    expect(screen.getAllByText("Ticket Count").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Status Filter").length).toBeGreaterThan(0);
    expect(screen.getByText("Executed Steps")).toBeInTheDocument();
    expect(screen.getByText("Final Step")).toBeInTheDocument();
    expect(screen.getAllByText("2").length).toBeGreaterThan(0);
    expect(screen.getAllByText("TICKET-0001 [open] payment-service").length).toBeGreaterThan(0);
    expect(screen.getAllByText("TICKET-0002 [open] checkout-api").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Ticket Id").length).toBeGreaterThan(0);
  });

  it("surfaces supporting search context for multistep ticket creation", () => {
    render(
      <QueryView
        documents={[
          {
            filename: "rag_overview.md",
            size_bytes: 1024,
            suffix: ".md",
          },
        ]}
        queryFilename=""
        question="Search docs for RAG and create a high severity ticket for payment-service"
        topK={3}
        activePresetQuestions={["Search docs for RAG and create a high severity ticket for payment-service"]}
        queryResult={null}
        agentQueryResult={{
          question: "Search docs for RAG and create a high severity ticket for payment-service",
          workflow_status: "completed",
          route: {
            route_type: "tool_execution",
            route_reason: "Search and execution requests should go through tool execution.",
            filename: null,
          },
          workflow_trace: [
            {
              stage: "routing",
              status: "completed",
              timestamp: "2026-03-15T00:00:00+00:00",
              detail: "Request routed to tool_execution.",
            },
          ],
          tool_chain: [
            {
              step_id: "step_1",
              step_index: 1,
              step_status: "completed",
              attempt_count: 1,
              retried: false,
              started_at: "2026-03-15T00:00:00+00:00",
              completed_at: "2026-03-15T00:00:00+00:00",
              question: "Search docs for RAG",
              tool_plan: {
                question: "Search docs for RAG",
                planning_mode: "heuristic_stub",
                route_hint: "tool_execution",
                tool_name: "document_search",
                action: "query",
                target: "RAG",
                arguments: {},
                plan_summary: "Plan document_search:query for RAG using a local heuristic planner.",
              },
              tool_execution: {
                tool_name: "document_search",
                action: "query",
                target: "RAG",
                execution_status: "completed",
                execution_mode: "local_adapter",
                result_summary: "Found 2 matching document(s) for 'RAG'.",
                trace_id: "trace-step-1",
                executed_at: "2026-03-15T00:00:00+00:00",
                output: {
                  query: "RAG",
                  matched_count: "2",
                  matched_documents: "rag_overview.md, test_chunk.txt",
                  snippets: "rag_overview.md: Retrieval-augmented generation, or RAG, is ...",
                },
              },
            },
            {
              step_id: "step_2",
              step_index: 2,
              step_status: "completed",
              attempt_count: 1,
              retried: false,
              started_at: "2026-03-15T00:00:00+00:00",
              completed_at: "2026-03-15T00:00:00+00:00",
              question: "create a high severity ticket for payment-service",
              tool_plan: {
                question: "create a high severity ticket for payment-service",
                planning_mode: "heuristic_stub",
                route_hint: "tool_execution",
                tool_name: "ticketing",
                action: "create",
                target: "payment-service",
                arguments: {
                  severity: "high",
                  supporting_query: "RAG",
                  supporting_documents: "rag_overview.md, test_chunk.txt",
                  supporting_snippets: "rag_overview.md: Retrieval-augmented generation, or RAG, is ...",
                  supporting_match_count: "2",
                },
                plan_summary: "Plan ticketing:create for payment-service using a local heuristic planner.",
              },
              tool_execution: {
                tool_name: "ticketing",
                action: "create",
                target: "payment-service",
                execution_status: "completed",
                execution_mode: "local_adapter",
                result_summary: "Created local ticket TICKET-0003 for payment-service.",
                trace_id: "trace-step-2",
                executed_at: "2026-03-15T00:00:00+00:00",
                output: {
                  ticket_id: "TICKET-0003",
                  status: "open",
                  severity: "high",
                  environment: "unspecified",
                  supporting_query: "RAG",
                  supporting_documents: "rag_overview.md, test_chunk.txt",
                  supporting_snippets: "rag_overview.md: Retrieval-augmented generation, or RAG, is ...",
                  supporting_match_count: "2",
                },
              },
            },
          ],
          tool_plan: {
            question: "create a high severity ticket for payment-service",
            planning_mode: "heuristic_stub",
            route_hint: "tool_execution",
            tool_name: "ticketing",
            action: "create",
            target: "payment-service",
            arguments: {
              severity: "high",
              supporting_query: "RAG",
              supporting_documents: "rag_overview.md, test_chunk.txt",
              supporting_snippets: "rag_overview.md: Retrieval-augmented generation, or RAG, is ...",
              supporting_match_count: "2",
            },
            plan_summary: "Plan ticketing:create for payment-service using a local heuristic planner.",
          },
          tool_execution: {
            tool_name: "ticketing",
            action: "create",
            target: "payment-service",
            execution_status: "completed",
            execution_mode: "local_adapter",
            result_summary: "Created local ticket TICKET-0003 for payment-service.",
            trace_id: "trace-final",
            executed_at: "2026-03-15T00:00:00+00:00",
            output: {
              ticket_id: "TICKET-0003",
              status: "open",
              severity: "high",
              environment: "unspecified",
              supporting_query: "RAG",
              supporting_documents: "rag_overview.md, test_chunk.txt",
              supporting_snippets: "rag_overview.md: Retrieval-augmented generation, or RAG, is ...",
              supporting_match_count: "2",
            },
          },
        }}
        agentWorkflowRuns={[]}
        diagnosticsResult={null}
        queryError=""
        queryBusy={false}
        onChangeDocument={vi.fn()}
        onChangeQuestion={vi.fn()}
        onChangeTopK={vi.fn()}
        onClearDiagnostics={vi.fn()}
        onSubmitQuery={(event) => event.preventDefault()}
        onRunAgent={vi.fn()}
        onLoadAgentWorkflowRun={vi.fn()}
        onRecoverAgentWorkflowRun={vi.fn()}
        onRunDiagnostics={vi.fn()}
      />,
    );

    expect(screen.getAllByText("Supporting Context").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Search Query").length).toBeGreaterThan(0);
    expect(screen.getAllByText("RAG").length).toBeGreaterThan(0);
    expect(screen.getAllByText("rag_overview.md, test_chunk.txt").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Search Snippets").length).toBeGreaterThan(0);
    expect(screen.queryByText("supporting_query")).not.toBeInTheDocument();
  });

  it("allows agent workflows without document context while keeping retrieval actions disabled", () => {
    render(
      <QueryView
        documents={[
          {
            filename: "rag_overview.md",
            size_bytes: 1024,
            suffix: ".md",
          },
        ]}
        queryFilename=""
        question="Check system status"
        topK={3}
        activePresetQuestions={["Check system status"]}
        queryResult={null}
        agentQueryResult={null}
        agentWorkflowRuns={[]}
        diagnosticsResult={null}
        queryError=""
        queryBusy={false}
        onChangeDocument={vi.fn()}
        onChangeQuestion={vi.fn()}
        onChangeTopK={vi.fn()}
        onClearDiagnostics={vi.fn()}
        onSubmitQuery={(event) => event.preventDefault()}
        onRunAgent={vi.fn()}
        onLoadAgentWorkflowRun={vi.fn()}
        onRecoverAgentWorkflowRun={vi.fn()}
        onRunDiagnostics={vi.fn()}
      />,
    );

    expect(screen.getAllByText("No document context (Agent optional)").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: "Run Query" }).at(-1)).toBeDisabled();
    expect(screen.getAllByRole("button", { name: "Run Diagnostics" }).at(-1)).toBeDisabled();
    expect(screen.getAllByRole("button", { name: "Run Agent" }).at(-1)).toBeEnabled();
    expect(
      screen.getAllByText(/No document context selected\. Retrieval-only actions are disabled/i).length,
    ).toBeGreaterThan(0);
  });

  it("renders recent workflow runs and loads a selected run", async () => {
    const user = userEvent.setup();
    const onLoadAgentWorkflowRun = vi.fn();

    render(
      <QueryView
        documents={[]}
        queryFilename=""
        question="Check system status"
        topK={3}
        activePresetQuestions={["Check system status"]}
        queryResult={null}
        agentQueryResult={null}
        agentWorkflowRuns={[
          {
            run_id: "run-2",
            question: "Create a ticket for the payment service outage",
            resumed_from_question: null,
            source_run_id: null,
            workflow_status: "completed",
            route_type: "tool_execution",
            route_reason: "Tool execution route.",
            filename: null,
            answered_at: null,
          },
        ]}
        diagnosticsResult={null}
        queryError=""
        queryBusy={false}
        onChangeDocument={vi.fn()}
        onChangeQuestion={vi.fn()}
        onChangeTopK={vi.fn()}
        onClearDiagnostics={vi.fn()}
        onSubmitQuery={(event) => event.preventDefault()}
        onRunAgent={vi.fn()}
        onLoadAgentWorkflowRun={onLoadAgentWorkflowRun}
        onRecoverAgentWorkflowRun={vi.fn()}
        onRunDiagnostics={vi.fn()}
      />,
    );

    expect(screen.getAllByText("Recent Workflow Runs").length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: "Load Run" }));

    expect(onLoadAgentWorkflowRun).toHaveBeenCalledWith("run-2");
  });

  it("renders workflow recovery semantics for current and recent runs", () => {
    render(
      <QueryView
        documents={[]}
        queryFilename=""
        question="Search docs for RAG and create a high severity ticket for payment-service"
        topK={3}
        activePresetQuestions={["Search docs for RAG and create a high severity ticket for payment-service"]}
        queryResult={null}
        agentQueryResult={{
          run_id: "run-recovery",
          root_run_id: "run-recovery",
          recovery_depth: 0,
          question: "Search docs for RAG and create a high severity ticket for payment-service",
          workflow_status: "failed",
          outcome_category: "recoverable_failure",
          retry_state: "retry_exhausted",
          recommended_recovery_action: "resume_from_failed_step",
          available_recovery_actions: ["resume_from_failed_step", "manual_retrigger"],
          recovery_action_details: {
            resume_from_failed_step: {
              workflow_kind: "search_then_ticket",
              target_step_index: 2,
              reused_step_indices: [1],
            },
          },
          resumed_from_step_index: null,
          reused_step_indices: [],
          failure_stage: "tool_execution",
          failure_message: "RuntimeError: debug injected persistent failure",
          route: {
            route_type: "tool_execution",
            route_reason: "Search and execution requests should go through tool execution.",
            filename: null,
          },
          workflow_trace: [],
          tool_chain: [],
        }}
        agentWorkflowRuns={[
          {
            run_id: "run-2",
            root_run_id: "run-2",
            recovery_depth: 0,
            question: "Search docs for RAG and create a high severity ticket for payment-service",
            resumed_from_question: null,
            source_run_id: null,
            resume_source_type: null,
            resume_strategy: null,
            resumed_from_step_index: null,
            reused_step_indices: [],
            applied_clarification_fields: [],
            question_rewritten: false,
            overridden_plan_arguments: [],
            workflow_status: "failed",
            terminal_reason: "tool_execution_failed",
            outcome_category: "recoverable_failure",
            is_recoverable: true,
            retry_state: "retry_exhausted",
            recommended_recovery_action: "resume_from_failed_step",
            available_recovery_actions: ["resume_from_failed_step", "manual_retrigger"],
            failure_stage: "tool_execution",
            failure_message: "RuntimeError: debug injected persistent failure",
            started_at: "2026-03-16T00:00:00+00:00",
            completed_at: "2026-03-16T00:00:01+00:00",
            last_updated_at: "2026-03-16T00:00:01+00:00",
            workflow_planning_mode: "llm_gemini",
            tool_planning_mode: "llm_gemini",
            tool_planning_modes: ["llm_gemini", "llm_gemini"],
            clarification_planning_mode: null,
            planner_call_count: 3,
            tool_planner_call_count: 2,
            workflow_planning_latency_ms: 10,
            tool_planning_latency_ms: 20,
            clarification_planning_latency_ms: 0,
            planner_latency_ms_total: 30,
            llm_planner_layers: ["workflow", "tool"],
            fallback_planner_layers: [],
            llm_tool_planner_steps: [1, 2],
            fallback_tool_planner_steps: [],
            retry_count: 1,
            retried_step_indices: [2],
            step_count: 2,
            route_type: "tool_execution",
            route_reason: "Tool execution route.",
            filename: null,
            answered_at: null,
            answer_source: null,
            final_tool_name: "ticketing",
            final_tool_action: "create",
          },
        ]}
        diagnosticsResult={null}
        queryError=""
        queryBusy={false}
        onChangeDocument={vi.fn()}
        onChangeQuestion={vi.fn()}
        onChangeTopK={vi.fn()}
        onClearDiagnostics={vi.fn()}
        onSubmitQuery={(event) => event.preventDefault()}
        onRunAgent={vi.fn()}
        onLoadAgentWorkflowRun={vi.fn()}
        onRecoverAgentWorkflowRun={vi.fn()}
        onRunDiagnostics={vi.fn()}
      />,
    );

    expect(screen.getAllByText("Recovery Semantics").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Resume From Failed Step (resume_from_failed_step)").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Manual Retrigger (manual_retrigger)").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Root Run").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Recovery Depth").length).toBeGreaterThan(0);
    expect(screen.getAllByText("run-recovery").length).toBeGreaterThan(0);
    expect(screen.getByText(/Failure:/)).toBeInTheDocument();
    expect(screen.getByText("Recovery Details")).toBeInTheDocument();
  });

  it("renders resumed workflow record fields without losing the real step index", async () => {
    const user = userEvent.setup();
    const onLoadAgentWorkflowRun = vi.fn();

    render(
      <QueryView
        documents={[]}
        queryFilename=""
        question="Search docs for RAG and create a high severity ticket for payment-service"
        topK={3}
        activePresetQuestions={["Search docs for RAG and create a high severity ticket for payment-service"]}
        queryResult={null}
        agentQueryResult={{
          run_id: "run-resumed",
          root_run_id: "source-run",
          recovery_depth: 1,
          question: "Search docs for RAG and create a high severity ticket for payment-service",
          resumed_from_question:
            "Search docs for RAG and create a high severity ticket for payment-service",
          source_run_id: "source-run",
          recovered_via_action: "resume_from_failed_step",
          resume_source_type: "run_id",
          resume_strategy: "search_then_ticket_failed_step_resume",
          resumed_from_step_index: 2,
          reused_step_indices: [1],
          question_rewritten: false,
          workflow_status: "completed",
          recommended_recovery_action: "none",
          available_recovery_actions: [],
          route: {
            route_type: "tool_execution",
            route_reason: "Tool execution route.",
            filename: null,
          },
          workflow_trace: [],
          tool_plan: {
            question: "create a high severity ticket for payment-service",
            planning_mode: "llm_gemini",
            route_hint: "tool_execution",
            tool_name: "ticketing",
            action: "create",
            target: "payment-service",
            arguments: {
              severity: "high",
              supporting_query: "RAG",
            },
            plan_summary: "Plan ticketing:create for payment-service using a llm planner.",
          },
          tool_execution: {
            tool_name: "ticketing",
            action: "create",
            target: "payment-service",
            execution_status: "completed",
            execution_mode: "local_adapter",
            result_summary: "Created local ticket TICKET-0204 for payment-service.",
            trace_id: "trace-final",
            executed_at: "2026-03-16T00:00:00+00:00",
            output: {
              ticket_id: "TICKET-0204",
              status: "open",
              severity: "high",
              environment: "unspecified",
              supporting_query: "RAG",
            },
          },
          tool_chain: [
            {
              step_id: "step_2",
              step_index: 2,
              step_status: "completed",
              attempt_count: 1,
              retried: false,
              started_at: "2026-03-16T00:00:00+00:00",
              completed_at: "2026-03-16T00:00:00+00:00",
              question: "create a high severity ticket for payment-service",
              tool_plan: {
                question: "create a high severity ticket for payment-service",
                planning_mode: "llm_gemini",
                route_hint: "tool_execution",
                tool_name: "ticketing",
                action: "create",
                target: "payment-service",
                arguments: {
                  severity: "high",
                  supporting_query: "RAG",
                },
                plan_summary: "Plan ticketing:create for payment-service using a llm planner.",
              },
              tool_execution: {
                tool_name: "ticketing",
                action: "create",
                target: "payment-service",
                execution_status: "completed",
                execution_mode: "local_adapter",
                result_summary: "Created local ticket TICKET-0204 for payment-service.",
                trace_id: "trace-step-2",
                executed_at: "2026-03-16T00:00:00+00:00",
                output: {
                  ticket_id: "TICKET-0204",
                  status: "open",
                  severity: "high",
                  environment: "unspecified",
                  supporting_query: "RAG",
                },
              },
            },
          ],
        }}
        agentWorkflowRuns={[]}
        diagnosticsResult={null}
        queryError=""
        queryBusy={false}
        onChangeDocument={vi.fn()}
        onChangeQuestion={vi.fn()}
        onChangeTopK={vi.fn()}
        onClearDiagnostics={vi.fn()}
        onSubmitQuery={(event) => event.preventDefault()}
        onRunAgent={vi.fn()}
        onLoadAgentWorkflowRun={onLoadAgentWorkflowRun}
        onRecoverAgentWorkflowRun={vi.fn()}
        onRunDiagnostics={vi.fn()}
      />,
    );

    expect(screen.getAllByText("Step 2").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Recovered Via").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Resume From Failed Step").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Search Then Ticket Failed-Step Resume").length).toBeGreaterThan(0);
    expect(screen.getByText("search_then_ticket_failed_step_resume")).toBeInTheDocument();
    expect(screen.getAllByText("source-run").length).toBeGreaterThan(0);
    expect(screen.getAllByText("1").length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: "Load Root Run" }));
    await user.click(screen.getByRole("button", { name: "Load Source Run" }));

    expect(onLoadAgentWorkflowRun).toHaveBeenNthCalledWith(1, "source-run");
    expect(onLoadAgentWorkflowRun).toHaveBeenNthCalledWith(2, "source-run");
  });

  it("renders a recovery chain for the current workflow and loads related runs", async () => {
    const user = userEvent.setup();
    const onLoadAgentWorkflowRun = vi.fn();

    render(
      <QueryView
        documents={[]}
        queryFilename=""
        question="Search docs for RAG and create a high severity ticket for payment-service"
        topK={3}
        activePresetQuestions={["Search docs for RAG and create a high severity ticket for payment-service"]}
        queryResult={null}
        agentQueryResult={{
          run_id: "run-depth-2",
          root_run_id: "run-root",
          recovery_depth: 2,
          question: "Search docs for RAG and create a high severity ticket for payment-service",
          resumed_from_question:
            "Search docs for RAG and create a high severity ticket for payment-service",
          source_run_id: "run-depth-1",
          recovered_via_action: "resume_from_failed_step",
          resume_source_type: "run_id",
          resume_strategy: "search_then_ticket_failed_step_resume",
          resumed_from_step_index: 2,
          reused_step_indices: [1],
          question_rewritten: false,
          workflow_status: "completed",
          recommended_recovery_action: "none",
          available_recovery_actions: [],
          route: {
            route_type: "tool_execution",
            route_reason: "Tool execution route.",
            filename: null,
          },
          workflow_trace: [],
          tool_chain: [],
        }}
        agentWorkflowRuns={[
          {
            run_id: "run-root",
            root_run_id: "run-root",
            recovery_depth: 0,
            question: "Search docs for RAG and create a high severity ticket for payment-service",
            workflow_status: "failed",
            route_type: "tool_execution",
            route_reason: "Tool execution route.",
            recommended_recovery_action: "resume_from_failed_step",
            available_recovery_actions: ["resume_from_failed_step", "manual_retrigger"],
          },
          {
            run_id: "run-depth-1",
            root_run_id: "run-root",
            recovery_depth: 1,
            question: "Search docs for RAG and create a high severity ticket for payment-service",
            resumed_from_question:
              "Search docs for RAG and create a high severity ticket for payment-service",
            source_run_id: "run-root",
            recovered_via_action: "resume_from_failed_step",
            resume_strategy: "search_then_ticket_failed_step_resume",
            workflow_status: "completed",
            route_type: "tool_execution",
            route_reason: "Tool execution route.",
            recommended_recovery_action: "none",
            available_recovery_actions: [],
          },
        ]}
        diagnosticsResult={null}
        queryError=""
        queryBusy={false}
        onChangeDocument={vi.fn()}
        onChangeQuestion={vi.fn()}
        onChangeTopK={vi.fn()}
        onClearDiagnostics={vi.fn()}
        onSubmitQuery={(event) => event.preventDefault()}
        onRunAgent={vi.fn()}
        onLoadAgentWorkflowRun={onLoadAgentWorkflowRun}
        onRecoverAgentWorkflowRun={vi.fn()}
        onRunDiagnostics={vi.fn()}
      />,
    );

    expect(screen.getAllByText("Recovery Chain").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Current Run").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Root Run").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Source Run").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Previous Chain Run" })).toBeInTheDocument();

    const chainButtons = screen.getAllByRole("button", { name: "Load Chain Run" });
    expect(chainButtons).toHaveLength(2);

    await user.click(screen.getByRole("button", { name: "Previous Chain Run" }));
    await user.click(chainButtons[0]);
    await user.click(chainButtons[1]);

    expect(onLoadAgentWorkflowRun).toHaveBeenNthCalledWith(1, "run-depth-1");
    expect(onLoadAgentWorkflowRun).toHaveBeenNthCalledWith(2, "run-root");
    expect(onLoadAgentWorkflowRun).toHaveBeenNthCalledWith(3, "run-depth-1");
  });

  it("runs recovery actions for current and recent workflow runs", async () => {
    const user = userEvent.setup();
    const onRecoverAgentWorkflowRun = vi.fn();

    render(
      <QueryView
        documents={[]}
        queryFilename=""
        question="Create a ticket for the payment service outage"
        topK={3}
        activePresetQuestions={["Create a ticket for the payment service outage"]}
        queryResult={null}
        agentQueryResult={{
          run_id: "run-current",
          question: "Create a ticket for the payment service outage",
          workflow_status: "failed",
          recommended_recovery_action: "manual_retrigger",
          available_recovery_actions: ["manual_retrigger"],
          route: {
            route_type: "tool_execution",
            route_reason: "Tool execution route.",
            filename: null,
          },
          workflow_trace: [],
          tool_chain: [],
        }}
        agentWorkflowRuns={[
          {
            run_id: "run-list",
            question: "Search docs for RAG and create a high severity ticket for payment-service",
            workflow_status: "failed",
            route_type: "tool_execution",
            route_reason: "Tool execution route.",
            recommended_recovery_action: "resume_from_failed_step",
            available_recovery_actions: ["resume_from_failed_step", "manual_retrigger"],
          },
        ]}
        diagnosticsResult={null}
        queryError=""
        queryBusy={false}
        onChangeDocument={vi.fn()}
        onChangeQuestion={vi.fn()}
        onChangeTopK={vi.fn()}
        onClearDiagnostics={vi.fn()}
        onSubmitQuery={(event) => event.preventDefault()}
        onRunAgent={vi.fn()}
        onLoadAgentWorkflowRun={vi.fn()}
        onRecoverAgentWorkflowRun={onRecoverAgentWorkflowRun}
        onRunDiagnostics={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Recover run-current Manual Retrigger" }));
    await user.click(
      screen.getByRole("button", { name: "Recover run-list Resume From Failed Step" }),
    );

    expect(onRecoverAgentWorkflowRun).toHaveBeenNthCalledWith(1, "run-current", "manual_retrigger");
    expect(onRecoverAgentWorkflowRun).toHaveBeenNthCalledWith(
      2,
      "run-list",
      "resume_from_failed_step",
    );
  });

  it("filters recent workflow runs by search and recovery action", async () => {
    const user = userEvent.setup();

    render(
      <QueryView
        documents={[]}
        queryFilename=""
        question="Check system status"
        topK={3}
        activePresetQuestions={["Check system status"]}
        queryResult={null}
        agentQueryResult={null}
        agentWorkflowRuns={[
          {
            run_id: "run-alpha",
            question: "Search docs for RAG and create a high severity ticket for payment-service",
            workflow_status: "failed",
            route_type: "tool_execution",
            route_reason: "Tool execution route.",
            recommended_recovery_action: "resume_from_failed_step",
            available_recovery_actions: ["resume_from_failed_step", "manual_retrigger"],
          },
          {
            run_id: "run-beta",
            question: "Create a ticket for the payment service outage",
            workflow_status: "failed",
            route_type: "tool_execution",
            route_reason: "Tool execution route.",
            recommended_recovery_action: "manual_retrigger",
            available_recovery_actions: ["manual_retrigger"],
          },
        ]}
        diagnosticsResult={null}
        queryError=""
        queryBusy={false}
        onChangeDocument={vi.fn()}
        onChangeQuestion={vi.fn()}
        onChangeTopK={vi.fn()}
        onClearDiagnostics={vi.fn()}
        onSubmitQuery={(event) => event.preventDefault()}
        onRunAgent={vi.fn()}
        onLoadAgentWorkflowRun={vi.fn()}
        onRecoverAgentWorkflowRun={vi.fn()}
        onRunDiagnostics={vi.fn()}
      />,
    );

    const recentRunsPanel = screen
      .getAllByRole("heading", { name: "Recent Workflow Runs" })
      .at(-1)
      ?.closest("article");
    expect(recentRunsPanel).not.toBeNull();
    const recentRuns = within(recentRunsPanel!);

    await user.selectOptions(recentRuns.getByLabelText("Recovery Filter"), "manual_retrigger");
    expect(
      recentRuns.getAllByText("Create a ticket for the payment service outage").length,
    ).toBeGreaterThan(0);
    expect(
      recentRuns.queryAllByText(
        "Search docs for RAG and create a high severity ticket for payment-service",
      ).length,
    ).toBe(0);

    await user.clear(recentRuns.getByLabelText("Run Search"));
    await user.type(recentRuns.getByLabelText("Run Search"), "alpha");
    expect(recentRuns.getByText("No matching workflow runs")).toBeInTheDocument();
  });

  it("focuses recent workflow runs on the current recovery chain", async () => {
    const user = userEvent.setup();

    render(
      <QueryView
        documents={[]}
        queryFilename=""
        question="Search docs for RAG and create a high severity ticket for payment-service"
        topK={3}
        activePresetQuestions={["Search docs for RAG and create a high severity ticket for payment-service"]}
        queryResult={null}
        agentQueryResult={{
          run_id: "run-depth-1",
          root_run_id: "run-root",
          recovery_depth: 1,
          question: "Search docs for RAG and create a high severity ticket for payment-service",
          resumed_from_question:
            "Search docs for RAG and create a high severity ticket for payment-service",
          source_run_id: "run-root",
          recovered_via_action: "resume_from_failed_step",
          resume_source_type: "run_id",
          resume_strategy: "search_then_ticket_failed_step_resume",
          workflow_status: "completed",
          recommended_recovery_action: "none",
          available_recovery_actions: [],
          route: {
            route_type: "tool_execution",
            route_reason: "Tool execution route.",
            filename: null,
          },
          workflow_trace: [],
          tool_chain: [],
        }}
        agentWorkflowRuns={[
          {
            run_id: "run-root",
            root_run_id: "run-root",
            recovery_depth: 0,
            question: "Search docs for RAG and create a high severity ticket for payment-service",
            workflow_status: "failed",
            route_type: "tool_execution",
            route_reason: "Tool execution route.",
            recommended_recovery_action: "resume_from_failed_step",
            available_recovery_actions: ["resume_from_failed_step", "manual_retrigger"],
          },
          {
            run_id: "run-depth-1",
            root_run_id: "run-root",
            recovery_depth: 1,
            question: "Search docs for RAG and create a high severity ticket for payment-service",
            resumed_from_question:
              "Search docs for RAG and create a high severity ticket for payment-service",
            source_run_id: "run-root",
            recovered_via_action: "resume_from_failed_step",
            resume_strategy: "search_then_ticket_failed_step_resume",
            workflow_status: "completed",
            route_type: "tool_execution",
            route_reason: "Tool execution route.",
            recommended_recovery_action: "none",
            available_recovery_actions: [],
          },
          {
            run_id: "run-other",
            root_run_id: "run-other",
            recovery_depth: 0,
            question: "Create a ticket for the payment service outage",
            workflow_status: "failed",
            route_type: "tool_execution",
            route_reason: "Tool execution route.",
            recommended_recovery_action: "manual_retrigger",
            available_recovery_actions: ["manual_retrigger"],
          },
        ]}
        diagnosticsResult={null}
        queryError=""
        queryBusy={false}
        onChangeDocument={vi.fn()}
        onChangeQuestion={vi.fn()}
        onChangeTopK={vi.fn()}
        onClearDiagnostics={vi.fn()}
        onSubmitQuery={(event) => event.preventDefault()}
        onRunAgent={vi.fn()}
        onLoadAgentWorkflowRun={vi.fn()}
        onRecoverAgentWorkflowRun={vi.fn()}
        onRunDiagnostics={vi.fn()}
      />,
    );

    const recentRunsPanel = screen
      .getAllByRole("heading", { name: "Recent Workflow Runs" })
      .at(-1)
      ?.closest("article");
    expect(recentRunsPanel).not.toBeNull();
    const recentRuns = within(recentRunsPanel!);

    expect(
      recentRuns.getAllByText("Create a ticket for the payment service outage").length,
    ).toBeGreaterThan(0);

    await user.click(
      recentRuns
        .getAllByRole("button")
        .find((button) => button.textContent?.includes("Focus Current Chain"))!,
    );

    expect(screen.getByText("Only runs from the current recovery chain are visible.")).toBeInTheDocument();
    expect(
      recentRuns.queryAllByText("Create a ticket for the payment service outage").length,
    ).toBe(0);

    await user.click(
      recentRuns
        .getAllByRole("button")
        .find((button) => button.textContent?.includes("Show All Chains"))!,
    );

    expect(
      recentRuns.getAllByText("Create a ticket for the payment service outage").length,
    ).toBeGreaterThan(0);
  });

  it("groups recent workflow runs by recovery chain and toggles chain visibility", async () => {
    const user = userEvent.setup();

    render(
      <QueryView
        documents={[]}
        queryFilename=""
        question="Search docs for RAG and create a high severity ticket for payment-service"
        topK={3}
        activePresetQuestions={["Search docs for RAG and create a high severity ticket for payment-service"]}
        queryResult={null}
        agentQueryResult={{
          run_id: "run-depth-1",
          root_run_id: "run-root",
          recovery_depth: 1,
          question: "Search docs for RAG and create a high severity ticket for payment-service",
          workflow_status: "completed",
          recommended_recovery_action: "none",
          available_recovery_actions: [],
          route: {
            route_type: "tool_execution",
            route_reason: "Tool execution route.",
            filename: null,
          },
          workflow_trace: [],
          tool_chain: [],
        }}
        agentWorkflowRuns={[
          {
            run_id: "run-root",
            root_run_id: "run-root",
            recovery_depth: 0,
            question: "Search docs for RAG and create a high severity ticket for payment-service",
            workflow_status: "failed",
            route_type: "tool_execution",
            route_reason: "Tool execution route.",
            recommended_recovery_action: "resume_from_failed_step",
            available_recovery_actions: ["resume_from_failed_step", "manual_retrigger"],
          },
          {
            run_id: "run-depth-1",
            root_run_id: "run-root",
            recovery_depth: 1,
            question: "Search docs for RAG and create a high severity ticket for payment-service",
            workflow_status: "completed",
            route_type: "tool_execution",
            route_reason: "Tool execution route.",
            recommended_recovery_action: "none",
            available_recovery_actions: [],
          },
          {
            run_id: "run-other",
            root_run_id: "run-other",
            recovery_depth: 0,
            question: "Create a ticket for the payment service outage",
            workflow_status: "failed",
            route_type: "tool_execution",
            route_reason: "Tool execution route.",
            recommended_recovery_action: "manual_retrigger",
            available_recovery_actions: ["manual_retrigger"],
          },
        ]}
        diagnosticsResult={null}
        queryError=""
        queryBusy={false}
        onChangeDocument={vi.fn()}
        onChangeQuestion={vi.fn()}
        onChangeTopK={vi.fn()}
        onClearDiagnostics={vi.fn()}
        onSubmitQuery={(event) => event.preventDefault()}
        onRunAgent={vi.fn()}
        onLoadAgentWorkflowRun={vi.fn()}
        onRecoverAgentWorkflowRun={vi.fn()}
        onRunDiagnostics={vi.fn()}
      />,
    );

    const recentRunsPanel = screen
      .getAllByRole("heading", { name: "Recent Workflow Runs" })
      .at(-1)
      ?.closest("article");
    expect(recentRunsPanel).not.toBeNull();
    const recentRuns = within(recentRunsPanel!);

    expect(recentRuns.getAllByText(/Chain Root:/).length).toBe(2);
    expect(recentRuns.getAllByText("Current Chain").length).toBeGreaterThan(0);
    expect(
      recentRuns.getAllByText("Search docs for RAG and create a high severity ticket for payment-service").length,
    ).toBeGreaterThan(0);

    await user.click(
      recentRuns
        .getAllByRole("button")
        .find((button) => button.textContent?.includes("Collapse Chain"))!,
    );

    expect(
      recentRuns.queryAllByText("Search docs for RAG and create a high severity ticket for payment-service").length,
    ).toBe(0);

    await user.click(
      recentRuns
        .getAllByRole("button")
        .find((button) => button.textContent?.includes("Expand Chain"))!,
    );

    expect(
      recentRuns.getAllByText("Search docs for RAG and create a high severity ticket for payment-service").length,
    ).toBeGreaterThan(0);
  });

  it("submits clarification recovery fields from the current workflow view", async () => {
    const user = userEvent.setup();
    const onRecoverAgentWorkflowRun = vi.fn();

    render(
      <QueryView
        documents={[]}
        queryFilename=""
        question="Search docs for payment-service outage and summarize top 2 results"
        topK={3}
        activePresetQuestions={["Search docs for payment-service outage and summarize top 2 results"]}
        queryResult={null}
        agentQueryResult={{
          run_id: "run-clarify",
          question: "Search docs for payment-service outage and summarize top 2 results",
          workflow_status: "clarification_required",
          recommended_recovery_action: "resume_with_clarification",
          available_recovery_actions: ["resume_with_clarification"],
          recovery_action_details: {
            resume_with_clarification: {
              missing_fields: ["search_query_refinement", "document_scope"],
            },
          },
          clarification_plan: {
            question: "Search docs for payment-service outage and summarize top 2 results",
            planning_mode: "llm_gemini",
            missing_fields: ["search_query_refinement", "document_scope"],
            follow_up_questions: [
              "What search query should I use?",
              "Which document should I search?",
            ],
            clarification_summary: "The workflow needs a refined query and document scope.",
          },
          route: {
            route_type: "tool_execution",
            route_reason: "Search requests should go through tool execution.",
            filename: null,
          },
          workflow_trace: [],
          tool_chain: [],
        }}
        agentWorkflowRuns={[]}
        diagnosticsResult={null}
        queryError=""
        queryBusy={false}
        onChangeDocument={vi.fn()}
        onChangeQuestion={vi.fn()}
        onChangeTopK={vi.fn()}
        onClearDiagnostics={vi.fn()}
        onSubmitQuery={(event) => event.preventDefault()}
        onRunAgent={vi.fn()}
        onLoadAgentWorkflowRun={vi.fn()}
        onRecoverAgentWorkflowRun={onRecoverAgentWorkflowRun}
        onRunDiagnostics={vi.fn()}
      />,
    );

    await user.type(screen.getByLabelText("Search Query Refinement"), "RAG");
    await user.type(screen.getByLabelText("Document Scope"), "rag_overview.md");
    await user.click(
      screen.getByRole("button", { name: "Recover With Clarification: Resume With Clarification" }),
    );

    expect(onRecoverAgentWorkflowRun).toHaveBeenCalledWith("run-clarify", "resume_with_clarification", {
      search_query_refinement: "RAG",
      document_scope: "rag_overview.md",
    });
  });
});

