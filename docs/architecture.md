# Architecture

## Goal

Build an engineering-oriented agent runtime for internal knowledge retrieval, tool execution, workflow orchestration, recovery, and evaluation.

The intended end state is not a simple chat interface. The system is being shaped as a runtime with:

- a knowledge layer
- a routing and planning layer
- a tool execution layer
- a workflow orchestration layer
- a recovery and lineage layer
- persisted run state
- evaluation and observability surfaces

## Current System Shape

The current implementation is a local-first runtime composed of a FastAPI backend, a React console, local file-backed state, and optional model providers.

At a high level:

1. Documents are uploaded and stored locally.
2. Text is chunked and embeddings are persisted.
3. Retrieval services score and rerank candidate chunks.
4. A request is routed into retrieval, tool execution, or clarification.
5. Planner services may decompose the request into a tool action or supported workflow.
6. Tool adapters execute local actions.
7. Workflow runs are persisted with step records, planner metadata, trace events, and recovery lineage.
8. Evaluation services aggregate benchmark metrics and persist latest/history reports for dashboard reuse.

## Core Modules

### 1. Ingestion

Responsible for:

- document upload
- local file management
- text extraction
- chunk generation
- document preview support

Current notes:

- the active implementation is local-first
- supported document handling is sufficient for development and evaluation, not yet broad enterprise ingestion

### 2. Indexing

Responsible for:

- embedding generation
- persisted embedding artifacts
- chunk-to-embedding linkage
- local indexing metadata

Current notes:

- the current implementation persists embeddings as local artifacts
- a formal vector index or database-backed storage layer is not yet the primary path

### 3. Retrieval

Responsible for:

- retrieval over persisted embeddings
- retrieval diagnostics
- candidate scoring
- lightweight reranking
- context assembly for answer generation

Current notes:

- retrieval is already a stable base capability
- hybrid retrieval is still future work

### 4. LLM and Planner Layer

Responsible for:

- provider integration for Gemini and OpenAI
- answer generation
- tool planning
- clarification planning
- workflow planning
- fallback behavior when planner calls fail or are disabled

Current notes:

- planners can run with real model calls or local fallback logic
- workflow planner debug capture and planner caching already exist

### 5. Routing and Orchestration

Responsible for:

- request routing
- selecting retrieval, tool execution, clarification, or workflow behavior
- orchestrating step-by-step workflow execution
- applying guardrails and clarification rules
- recording workflow traces and terminal semantics

Current notes:

- this is the current center of gravity of the project
- supported multi-step flows are intentionally constrained to a small set of known workflow shapes
- retry and recovery semantics are now part of the runtime contract rather than ad hoc UI behavior

### 6. Tool Layer

Responsible for:

- adapter-style tool execution
- structured tool outputs
- action-specific argument handling
- local operational simulations for workflow testing

Current tools:

- `document_search`
- `system_status`
- `ticketing`

Current notes:

- these are local adapters, not real external integrations
- the architecture is moving toward clearer local-vs-real adapter boundaries

### 7. Recovery and Lineage

Responsible for:

- retry handling
- retry exhaustion semantics
- clarification-driven continuation
- failed-step resume for supported workflows
- manual retrigger recovery
- recovery lineage metadata and navigation

Current notes:

- recovery is now a first-class runtime behavior
- the current implementation supports a bounded set of recovery strategies rather than arbitrary rerun-from-step-N

### 8. State and Persistence

Responsible for:

- local workflow run persistence
- local ticket persistence
- artifact persistence for chunks and embeddings
- planner debug payload persistence
- evaluation overview cache persistence
- evaluation report persistence
- legacy workflow run migration support

Current notes:

- JSON-backed state is sufficient for iterative development
- a more formal repository or database-backed state layer is still ahead

### 9. Evaluation and Observability

Responsible for:

- retrieval evaluation
- route evaluation
- workflow evaluation
- tool execution evaluation
- overview and highlight metric aggregation
- latest and historical report persistence
- workflow trace inspection
- planner diagnostics and debug capture

Current notes:

- observability is already useful for development
- cost tracking and deeper analytics remain future work
- local benchmark persistence is already part of the day-to-day workflow

## Request Flow

### Knowledge Query Flow

1. Client sends a retrieval query.
2. Retrieval service loads persisted embeddings and scores candidate chunks.
3. The system reranks and returns matched chunks.
4. The answer layer returns either a model-backed answer or a fallback answer.

### Agent Request Flow

1. Client sends an agent request.
2. Router classifies the request.
3. Orchestrator either:
   - runs retrieval directly,
   - plans and executes a single tool action,
   - asks for clarification,
   - or decomposes the request into a supported workflow.
4. Planner layers may use LLM-backed planning or heuristic fallback.
5. Tool steps execute through local adapters.
6. The run is persisted with:
   - route information
   - workflow trace events
   - step records
   - planner modes and latencies
   - final terminal reason

### Recovery Flow

1. A workflow run may fail, require clarification, or exhaust retry.
2. The runtime assigns:
   - outcome category
   - retry state
   - recommended recovery action
   - available recovery actions
3. A client may recover by:
   - clarification continuation
   - failed-step resume
   - manual retrigger
4. Recovery executes as a new workflow run.
5. Recovery lineage metadata is attached so the relationship between runs remains inspectable and navigable.

### Evaluation Flow

1. A client selects an evaluation mode and dataset.
2. The evaluation service executes the benchmark against the current runtime.
3. The result is persisted as:
   - latest report
   - timestamped history snapshot
4. Overview and highlight services aggregate benchmark and runtime metrics.
5. The frontend dashboard loads:
   - overview metrics
   - highlight metrics
   - latest saved reports
   - recent history and previous-run deltas

## Design Principles

### Local-First Development

The system is optimized for local development and iterative agent engineering:

- local backend
- local frontend
- local file-backed state
- optional live model providers
- fallback behavior when providers are unavailable

### Explicit Fallbacks

The runtime should degrade rather than collapse:

- planner calls can fall back to heuristics
- answer generation can fall back to local responses
- workflow traces should explain which path was taken
- recovery guidance should remain explicit even when execution fails

### Observable Behavior

The system is designed to make agent behavior inspectable:

- persisted workflow runs
- planner mode visibility
- planner latency tracking
- step-level trace events
- debug capture for workflow planning
- persisted evaluation reports
- recovery lineage and chain visualization

### Incremental Runtime Maturity

The project is intentionally growing from a capable local runtime toward a more production-like agent system.

Current maturity is strongest in:

- retrieval
- routing
- local tool execution
- planner integration
- workflow traceability
- recovery semantics and lineage
- evaluation dashboards and persisted reports

The next maturity steps are:

- more general rerun policies
- more explicit runtime policies
- real external adapter boundaries
- stronger persistence abstractions
- tighter metric packaging and project documentation
