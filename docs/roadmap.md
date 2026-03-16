# Roadmap

This roadmap reflects the repository's current state rather than the original bootstrap plan.

## Phase 1: Foundation

Goal: establish a runnable local development skeleton.

Completed:

- FastAPI backend scaffold
- React frontend scaffold
- project configuration and environment loading
- base API routing and local development flow

Status:

- completed

## Phase 2: Document Pipeline

Goal: build a usable local document ingestion and indexing flow.

Completed:

- document upload and deletion
- local raw file persistence
- text extraction for supported text-style files
- chunk generation and chunk persistence
- embedding generation and embedding persistence
- document preview and artifact inspection APIs

Not yet a focus:

- formal vector database or production index storage
- broader file-type and ingestion pipeline coverage

Status:

- completed as a local-first implementation

## Phase 3: Retrieval and Knowledge Query

Goal: support retrieval-backed question answering with diagnostics.

Completed:

- vector-style retrieval over persisted embeddings
- retrieval diagnostics endpoint
- lightweight heuristic reranking
- fallback answer generation
- Gemini and OpenAI chat integration paths
- retrieval benchmark datasets and evaluation API

Still open:

- hybrid retrieval
- richer retrieval quality analytics

Status:

- completed as the current knowledge layer baseline

## Phase 4: Agent Runtime and Workflow Orchestration

Goal: evolve the retrieval system into an agent runtime with tools, planners, workflows, and recovery semantics.

Completed so far:

- request routing for retrieval, tool execution, and clarification
- local adapter-style tools:
  - `document_search`
  - `system_status`
  - `ticketing`
- structured tool planning and execution
- LLM-backed tool planner with fallback behavior
- LLM-backed clarification planner with fallback behavior
- LLM-backed workflow planner with fallback behavior
- multi-step workflow support for:
  - `search_then_ticket`
  - `search_then_summarize`
  - `status_then_ticket`
  - `status_then_summarize`
- ticket action support for:
  - `create`
  - `update`
  - `close`
- workflow run persistence
- workflow resume flows
- workflow run listing, lookup, stats, prune, reset, and migration
- planner mode, planner count, planner latency, and debug capture diagnostics
- clarification guardrails for search miss, summary miss, and unsupported direct actions

Still open:

- richer runtime recovery
- step retry
- rerun from step N
- broader workflow branching
- stronger separation between local and real tool adapters

Status:

- in progress
- core runtime is implemented and usable
- current focus is runtime maturity rather than first-time feature bring-up

## Phase 5: Evaluation and Observability

Goal: make the system measurable, inspectable, and easier to improve.

Completed so far:

- retrieval evaluation datasets and reports
- agent route evaluation datasets and reports
- agent workflow evaluation datasets and reports
- tool execution evaluation support
- frontend evaluation console
- planner diagnostics on persisted workflow runs
- workflow planner debug capture

Still open:

- systematic fallback-rate tracking
- broader latency and cost benchmarking
- more formal run analytics and trend reporting

Status:

- in progress
- evaluation coverage is already useful, but observability is not yet complete

## Near-Term Direction

The next set of iterations should stay focused on runtime maturity:

- tighten failure semantics and terminal reasons
- add step-level retry foundations
- improve resume toward failed-step continuation
- expand workflow coverage carefully, not broadly
- prepare cleaner boundaries for future real adapters and storage backends
