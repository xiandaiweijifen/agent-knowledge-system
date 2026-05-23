# Agent Knowledge System

An engineering-focused agent runtime for knowledge retrieval, tool execution, workflow orchestration, failure recovery, and evaluation.

## What This Project Is

This repository builds a local-first agent runtime for engineering and operations scenarios.

It is not just a RAG demo and not just a chat endpoint with a few prompts. The target shape is a system with:

- a document-backed knowledge layer
- an agent routing layer
- tool execution through adapter-style interfaces
- multi-step workflow orchestration
- planner fallback and debugability
- persisted runs, recovery behavior, and runtime diagnostics
- evaluation reports and benchmark dashboards

Today, the project already has a working backend, frontend console, local tool adapters, persisted workflow lineage, recoverable multi-step runs, and an evaluation dashboard with locally saved reports.

## Current State

The repository is in a late-stage refactor transition.

The default engineering direction is now `agent_v2`, which is built on:

- LangGraph for orchestration, checkpoints, interrupts, and state threading
- Qdrant-backed retrieval on the query path, with LlamaIndex still available as a compatibility path
- PostgreSQL/Redis hooks for runtime infrastructure
- LangSmith tracing
- SSE event streaming to the frontend query console

Implemented and usable today:

- document ingestion for local text-style documents, including `.txt`, `.md`,
  and `.json`
- persisted chunks and embeddings
- retrieval with diagnostics and lightweight reranking
- knowledge query and fallback answer paths
- request routing for retrieval, tool execution, and clarification
- local tool adapters for `document_search`, `system_status`, `service_dependencies`, and `ticketing`
- LLM-backed `tool planner`, `clarification planner`, and `workflow planner`
- fallback behavior when planner calls fail or are unavailable
- `agent_v2` runtime with:
  - LLM-first route selection
  - supervisor + specialist graph delegation
  - streaming execution events
  - checkpoint-backed resume
  - clarification interrupts
  - persisted run lookup and recovery lineage
- multi-step workflows for:
  - `search_then_ticket`
  - `search_then_summarize`
  - `status_then_ticket`
  - `status_then_summarize`
- retry semantics and retry-exhausted handling
- clarification-driven continuation
- failed-step resume for the current single-step `agent_v2` tool path
- manual retrigger recovery for failed `agent_v2` runs
- unified recovery entrypoint and recovery action semantics
- persisted workflow runs with trace events, lineage metadata, and maintenance endpoints
- retrieval, route, workflow, and tool-execution evaluation datasets with a frontend evaluation console
- locally persisted evaluation reports, overview caching, and benchmark history
- an incident triage workflow that combines service status, runbook evidence,
  imported external ticket evidence, ticket draft creation, and human-confirmed
  submission

Still intentionally unfinished:

- richer `agent_v2` recovery such as general rerun-from-step-N across true multi-step graphs
- real external system adapters
- broader multi-step `agent_v2` workflow branching and policy logic
- deeper cost and latency analytics
- production adapters for real monitoring and ticketing systems

Knowledge-layer status today:

- the project now uses `Qdrant` as the default primary retrieval backend in standard runtime mode
- document assets expose readiness for:
  - `chunks`
  - `embeddings`
  - `llamaindex`
  - `qdrant`
- chunking is now section-aware, and persisted knowledge nodes carry:
  - `section_title`
  - `section_path`
  - `heading_level`
  - `document_kind`
- retrieval supports both:
  - single-document lookup
  - corpus queries with `filename = null`
- retrieval ranking now includes:
  - query normalization
  - metadata-aware rerank bonus
  - source diversification
  - metadata-aware corpus filtering
  - document-level corpus bonus
- query results now surface grounded-answer features:
  - `answer_citations`
  - `groundedness_status`
  - `citation_coverage`
  - verification notes
- retrieval evaluation now distinguishes:
  - retrieval quality
  - grounded answer quality

Current knowledge-layer boundary:

- verification is signal-heavy rather than a strong independent verifier
- reranking is light-to-medium strength rather than a heavy second-stage ranker
- chunk/node modeling is structurally upgraded, but not yet hierarchical
- corpus retrieval is materially improved, but not yet fully corpus-native

Next knowledge-layer priority:

- continue pushing corpus retrieval toward a more corpus-native design over time

### Runtime Modes

The repository currently has two runtime surfaces:

- `legacy agent runtime`
  - still exists for backward compatibility, legacy maintenance endpoints, and older tests
- `agent_v2 runtime`
  - current default target for product behavior and active refactor work

Runtime selection is controlled through:

- `AGENT_DEFAULT_RUNTIME=legacy`
- `AGENT_DEFAULT_RUNTIME=v2`

When `AGENT_DEFAULT_RUNTIME=v2`, the default `/api/query/agent` entrypoints dispatch to `agent_v2` for normal execution, resume by `run_id`, run listing, and run lookup.

### Knowledge Index Backends

The repository keeps the knowledge pipeline local-first, but retrieval now
defaults to Qdrant while still preserving the historical LlamaIndex path for
compatibility and fallback testing.

Current knobs:

- `VECTOR_STORE_PROVIDER=qdrant`
- `KNOWLEDGE_WRITE_QDRANT=true`
- `KNOWLEDGE_WRITE_LLAMAINDEX=true`
- `QDRANT_URL=http://localhost:6333` for a local or remote Qdrant server
- `QDRANT_LOCAL_PATH=...` for local embedded development mode
  Relative paths are resolved from the repository root, not the current shell directory.
- `QDRANT_COLLECTION_NAME=agent_knowledge_chunks`
- for multi-process local work, batch import, and evaluation scripts, prefer `QDRANT_URL`
  over embedded `QDRANT_LOCAL_PATH`

## Core Capabilities

### 1. Knowledge Layer

- upload and preview local `.txt`, `.md`, and `.json` documents
- persist chunk artifacts
- persist embedding artifacts
- expose knowledge asset readiness for chunks, embeddings, LlamaIndex stores, and Qdrant sync
- retrieve relevant chunks for a question with Qdrant as the default primary mode
- run corpus retrieval without a fixed document context
- inspect retrieval diagnostics and ranked candidates
- return section-aware matches with document kind and corpus identity metadata
- generate grounded answers with citations and verification signals
- run fallback answering when no live model answer path is configured

The repository now also includes a small structured JSON corpus under
`data/raw/` for engineering-support testing. These JSON documents are intended
to exercise:

- JSON preview and flattening behavior
- chunking and embedding of structured records
- future workflow tests for service runtime review, dependency inspection, and
  ticket drafting

Included JSON corpus files:

- `engineering_service_catalog.json`
- `engineering_dependency_map.json`
- `engineering_incident_patterns.json`
- `engineering_runtime_review_cases.json`
- `engineering_ticket_templates.json`

### 2. Agent Layer

- route incoming requests into retrieval, tool execution, or clarification
- plan tool execution with either LLM or heuristic fallback
- plan clarification requests with either LLM or heuristic fallback
- plan workflow decomposition with either LLM or heuristic fallback

### 3. Tool Layer

Local adapter-style tools currently include:

- `document_search`
- `system_status`
- `service_dependencies`
- `ticketing`

The ticketing tool currently supports:

- `draft`
- `submit`
- `create`
- `update`
- `close`
- `query`
- `list`

`draft` and `submit` are the preferred incident workflow actions. The agent
prepares ticket drafts first, then waits for explicit user confirmation before
submitting the ticket.

Ticket records are persisted in `data/tool_state/tickets.json`. For local
inspection and demos, every created, drafted, submitted, updated, or closed
ticket also writes a readable markdown artifact and a JSON artifact under
`data/tool_state/tickets/`. These files are runtime artifacts and are ignored by
Git.

The `system_status` tool also supports scenario-based mock snapshots through an
optional `scenario` argument. This allows local runs to select different
predefined runtime states such as `healthy_baseline`, `timeout_spike`,
`db_latency_spike`, or `recovery_in_progress` without changing workflow logic.

The `service_dependencies` tool reads the structured engineering dependency
corpus from `engineering_dependency_map.json` and returns downstream dependency
records, likely failure signals, and recommended checks for a target service in
an environment such as `production`.

### 4. Workflow Runtime

The agent runtime already supports:

- single-step execution
- multi-step workflow traces
- workflow persistence
- resume metadata
- recovery lineage metadata
- previous/root/source run navigation
- terminal reasons and failure stages
- planner mode, planner count, and planner latency diagnostics
- retry state and recovery action semantics
- run listing, lookup, stats, pruning, reset, and schema migration

The runtime also now exposes an initial `skill` metadata layer. This does not
yet change execution behavior, but it adds stable response fields for:

- `workflow_family`
- `available_skills`
- `skill_trace`
- per-step `skill_id` / `skill_label`

This scaffolding is the compatibility layer for the next phase, where reusable
engineering-support skills will sit between tools and full workflows.

### 5. Incident Triage Workflow

The primary engineering-support scenario is `Incident Triage`.

Example request:

```text
Check payment-service in production for timeout issues and if it is abnormal prepare a high severity ticket draft
```

The `agent_v2` workflow executes:

1. `system_status:query`
   Inspect the requested service and environment using structured service status snapshots.
2. `document_search:query`
   Search the service runbook, such as `payment_service_runbook.md`, for symptom-specific evidence.
3. `document_search:query` with `search_mode=qdrant`
   Retrieve imported external support, incident, or issue records from Qdrant.
4. `ticketing:draft`
   Prepare an incident ticket draft with severity, environment, summary, and supporting evidence.
5. human confirmation
   Wait for the user to choose submit or cancel.
6. `ticketing:submit`
   Submit the prepared ticket only after explicit confirmation.

Internally, this workflow is now organized around three reusable skills:

- `review_service_health`
- `collect_incident_evidence`
- `prepare_incident_ticket`

Current evidence sources:

- service status snapshots from local mock service data
- curated service runbooks
- normalized external records from:
  - `customer_support_tickets`
  - `it_support_v2`
  - `bugsrepo_structured`

The frontend Query view renders this as a compact task panel with service
health, runbook evidence, imported ticket evidence, ticket draft details, and
submit/cancel controls.

### 6. Service Runtime Review Workflow

The second engineering-support scenario is `Service Runtime Review`.

Example request:

```text
Check payment-service in production status and tell me what to look at for timeout issues
```

The workflow currently executes:

1. `system_status:query`
   Inspect the service health, metrics, and active alerts for the requested environment.
2. `service_dependencies:query`
   Inspect the structured dependency map to identify the most likely downstream dependency to check next.
3. `document_search:query`
   Pull runbook guidance tied to the relevant symptom or service runbook.

The workflow returns a runtime review summary rather than creating a ticket. Its
goal is to answer:

- is the service healthy or degraded
- what evidence supports that conclusion
- what the operator should inspect next

Internally, this workflow reuses:

- `review_service_health`
- `inspect_service_dependencies`
- `collect_runtime_guidance`

### 7. Evaluation and Observability

- retrieval evaluation datasets and reports
- retrieval groundedness and citation coverage metrics
- agent route evaluation datasets and reports
- agent workflow evaluation datasets and reports
- tool execution evaluation datasets and reports
- evaluation overview, highlights, latest-result loading, and history
- workflow planner debug capture
- persisted workflow run inspection through API and frontend

## Architecture Snapshot

High-level backend flow:

1. Documents are uploaded and stored locally.
2. Text is chunked and embedding artifacts are persisted.
3. Qdrant-backed retrieval services score and rerank section-aware candidate chunks.
4. Corpus queries can merge and rank candidates across multiple documents with explicit corpus metadata.
5. Requests are routed into retrieval, clarification, or tool/workflow execution.
6. Answer generation synthesizes grounded responses with citations and verification signals.
7. Planner services decide tool or workflow behavior, with fallback paths if model planning fails.
8. Workflow runs are persisted with trace events, lineage metadata, and planner diagnostics.
9. Evaluation services aggregate benchmark results and persist latest/history reports for the dashboard.

## Recovery Model

The runtime distinguishes between:

- retryable tool failures
- recoverable workflow failures
- clarification-required pauses
- terminal failures

Supported recovery behavior today includes:

- retry with retry-exhausted semantics
- clarification-based continuation
- failed-step resume for the current single-step `agent_v2` tool path
- manual retrigger recovery for failed `agent_v2` runs
- clarification-based continuation
- persisted recovery lineage with `root_run_id`, `source_run_id`, `recovery_depth`, and `recovered_via_action`

Current `agent_v2` recovery boundary:

- supported:
  - `resume_with_clarification`
  - `resume_from_failed_step` for single-step failed tool execution
  - `manual_retrigger`
- not yet generalized:
  - step-N replay across true multi-step LangGraph workflows
  - legacy-style recovery semantics for every historical workflow shape

The frontend exposes these semantics through:

- recover actions on workflow runs
- recovery chain visualization
- chain focus and chain navigation
- root/source run loading shortcuts

## Evaluation Model

The evaluation layer currently has four benchmark modes:

- retrieval
- agent route
- agent workflow
- tool execution

For each supported benchmark mode, the system can:

- load local evaluation datasets
- run evaluation against the current runtime
- persist the latest report locally
- persist timestamped history snapshots
- surface deltas versus the previous run
- aggregate overview and highlight metrics for the dashboard

Stored evaluation artifacts live under:

- `data/eval/`
- `data/tool_state/evaluation_reports/`
- `data/tool_state/evaluation_overview_cache.json`
- `data/tool_state/evaluation_metrics_summary.json`

Main implementation areas:

- `backend/app/services/ingestion/`
- `backend/app/services/retrieval/`
- `backend/app/services/agent/`
- `backend/app/services/llm/`
- `backend/app/services/evaluation/`
- `frontend/src/`

## API Surface

### Health and System

- `GET /api/health`
- `GET /api/health/system`

### Documents and Pipeline

- `GET /api/documents`
- `GET /api/documents/{filename}`
- `POST /api/documents/upload`
- `DELETE /api/documents/{filename}`
- `GET /api/documents/{filename}/chunks`
- `POST /api/documents/{filename}/chunks/persist`
- `GET /api/documents/{filename}/chunks/persisted`
- `POST /api/documents/{filename}/embeddings/persist`
- `GET /api/documents/{filename}/embeddings/persisted`

### Query and Agent Runtime

- `POST /api/query`
- `POST /api/query/diagnostics`
- `POST /api/query/route`
- `POST /api/query/agent`
- `POST /api/query/agent/resume`
- `POST /api/query/agent/recover`
- `GET /api/query/agent/runs`
- `GET /api/query/agent/runs/{run_id}`
- `POST /api/query/agent/runs/migrate`
- `GET /api/query/agent/runs/stats`
- `POST /api/query/agent/runs/prune`
- `POST /api/query/agent/runs/reset`
- `POST /api/query/agent-v2`
- `POST /api/query/agent-v2/stream`
- `POST /api/query/agent-v2/resume`
- `POST /api/query/agent-v2/recover`
- `GET /api/query/agent-v2/runs`
- `GET /api/query/agent-v2/runs/{run_id}`

Notes:

- `/api/query/agent*` is the stable default surface.
- `/api/query/agent-v2*` is the explicit v2 surface.
- With `AGENT_DEFAULT_RUNTIME=v2`, the default `/api/query/agent*` surface routes normal query behavior through `agent_v2`.
- Recovery-capable frontend flows should prefer `/api/query/agent-v2/recover` as the explicit v2 control-plane surface.
- Legacy maintenance endpoints such as `runs/migrate`, `runs/stats`, `runs/prune`, and `runs/reset` still belong to the legacy control plane.

### Tools

- `GET /api/query/tools`
- `POST /api/query/tools/plan`
- `POST /api/query/tools/execute`

### Evaluation

- `GET /api/evaluation/retrieval/datasets`
- `POST /api/evaluation/retrieval`
- `GET /api/evaluation/retrieval/latest`
- `GET /api/evaluation/retrieval/history`
- Retrieval evaluation accepts an optional `vector_store_provider` so you can save
  and compare `qdrant` and `llamaindex` reports independently.
- `GET /api/evaluation/agent-route/datasets`
- `POST /api/evaluation/agent-route`
- `GET /api/evaluation/agent-route/latest`
- `GET /api/evaluation/agent-route/history`
- `GET /api/evaluation/agent-workflow/datasets`
- `POST /api/evaluation/agent-workflow`
- `GET /api/evaluation/agent-workflow/latest`
- `GET /api/evaluation/agent-workflow/history`
- `GET /api/evaluation/agent-tool-execution/datasets`
- `POST /api/evaluation/agent-tool-execution`
- `GET /api/evaluation/agent-tool-execution/latest`
- `GET /api/evaluation/agent-tool-execution/history`
- `GET /api/evaluation/overview`
- `GET /api/evaluation/metrics-summary`

## Tech Stack

- Backend: FastAPI
- Frontend: React + Vite
- Agent runtime: LangGraph + LangGraph checkpoints
- Retrieval: LlamaIndex-backed knowledge backbone with corpus retrieval, structured metadata, grounded citations, and verification signals
- LLM access: Gemini and OpenAI APIs, with local fallback paths
- State persistence today:
  - `agent_v2` runs persisted in JSON for easy inspection
  - LangGraph checkpointer wired for checkpoint resume
- Infra hooks:
  - PostgreSQL configuration for checkpoints
  - Redis configuration for runtime cache/session support
- Observability: LangSmith tracing + persisted local evaluation/report artifacts

## Local Setup

### Recommended Quick Start

Use this path for normal local development and workflow testing.

From the repo root, start the infrastructure:

```powershell
docker compose up -d qdrant postgres redis
docker compose ps
```

Start the backend in a second terminal:

```powershell
cd backend
.\.venv\Scripts\activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Start the frontend in a third terminal:

```powershell
cd frontend
npm run dev
```

Expected URLs:

- Backend API root: `http://127.0.0.1:8000/`
- OpenAPI docs: `http://127.0.0.1:8000/docs`
- Frontend console: `http://127.0.0.1:5173`

Equivalent helper scripts are also available from the repo root:

```powershell
bash scripts/run_backend.sh
bash scripts/run_frontend.sh
```

### Standard Runtime Mode

For normal project usage, start Docker first and treat `Qdrant + PostgreSQL + Redis`
as part of the standard runtime.

1. Start Docker Desktop.
2. From the repo root, start the full local infra set:

```powershell
docker compose up -d qdrant postgres redis
```

This starts:

- Qdrant on `localhost:6333`
- PostgreSQL on `localhost:5432`
- Redis on `localhost:6379`

3. Verify that all three containers are healthy before starting the app:

```powershell
docker compose ps
```

Expected containers:

- `aks_qdrant`
- `aks_postgres`
- `aks_redis`

4. Start the backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
$env:PYTHONPATH='.'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

5. Start the frontend:

```powershell
cd frontend
npm install
npm run dev
```

Recommended runtime switch:

```powershell
$env:AGENT_DEFAULT_RUNTIME='v2'
```

Use hot reload only when you are actively editing backend code:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

URLs:

- Backend API root: `http://127.0.0.1:8000/`
- OpenAPI docs: `http://127.0.0.1:8000/docs`
- Frontend console: `http://127.0.0.1:5173`

Startup notes:

- The backend is successfully started when you see:
  - `Application startup complete.`
  - `Uvicorn running on http://127.0.0.1:8000`
- In standard runtime mode, all three local services are expected to be reachable:
  - Qdrant for retrieval and corpus search
  - PostgreSQL for LangGraph checkpoint persistence
  - Redis for runtime cache/session infrastructure
- A healthy standard-runtime backend startup on Windows should also show:
  - `LangGraph checkpoint tables ready`
  - `Postgres checkpointer ready (sync fallback)`
  - `Redis client ready`
- If PostgreSQL or Redis are configured in `.env` but their containers are not
  running, startup may stall on `Waiting for application startup.`

To stop the standard local stack:

```powershell
docker compose stop qdrant postgres redis
```

### Minimal Development Mode

If you only want a lightweight local dev session, you can skip Docker and run in degraded mode.

Backend:

```powershell
cd backend
.\.venv\Scripts\activate
$env:PYTHONPATH='.'
uvicorn app.main:app
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

In this mode:

- leave `DATABASE_URL=` empty
- leave `REDIS_URL=` empty
- the backend still works for most query, evaluation, and frontend flows
- checkpoint persistence and Redis-backed runtime support are disabled

The frontend proxies `/api` requests to the local FastAPI backend by default.

## Environment Configuration

Create a repo-root `.env` file based on `.env.example`.

Recommended standard runtime setup:

```env
APP_ENV=development
AGENT_DEFAULT_RUNTIME=v2
EMBEDDING_PROVIDER=gemini
EMBEDDING_HTTP_TRUST_ENV=false
CHAT_PROVIDER=gemini
ROUTE_PLANNER_PROVIDER=gemini
TOOL_PLANNER_PROVIDER=gemini
CLARIFICATION_PLANNER_PROVIDER=gemini
WORKFLOW_PLANNER_PROVIDER=gemini
DATABASE_URL=postgresql://postgres:password@127.0.0.1:5432/agent_knowledge_system
REDIS_URL=redis://127.0.0.1:6379/0
QDRANT_URL=http://127.0.0.1:6333
QDRANT_LOCAL_PATH=
```

Minimal development setup:

```env
APP_ENV=development
AGENT_DEFAULT_RUNTIME=v2
EMBEDDING_PROVIDER=mock
CHAT_PROVIDER=fallback
ROUTE_PLANNER_PROVIDER=fallback
TOOL_PLANNER_PROVIDER=fallback
CLARIFICATION_PLANNER_PROVIDER=fallback
WORKFLOW_PLANNER_PROVIDER=fallback
DATABASE_URL=
REDIS_URL=
```

Example Gemini/OpenAI model setup:

```env
EMBEDDING_PROVIDER=gemini
EMBEDDING_HTTP_TRUST_ENV=false
CHAT_PROVIDER=gemini
TOOL_PLANNER_PROVIDER=gemini
CLARIFICATION_PLANNER_PROVIDER=gemini
WORKFLOW_PLANNER_PROVIDER=gemini

GEMINI_API_KEY=your_key
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GEMINI_CHAT_MODEL=gemini-2.5-flash-lite
GEMINI_TOOL_PLANNER_MODEL=
GEMINI_CLARIFICATION_PLANNER_MODEL=
GEMINI_WORKFLOW_PLANNER_MODEL=

OPENAI_API_KEY=
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-4o-mini
OPENAI_TOOL_PLANNER_MODEL=
OPENAI_CLARIFICATION_PLANNER_MODEL=
OPENAI_WORKFLOW_PLANNER_MODEL=
```

Only set `DATABASE_URL` and `REDIS_URL` when:

- the Docker `postgres` and `redis` containers are already running, or
- you already have reachable local Postgres/Redis instances

Current local startup behavior:

- `DATABASE_URL` empty: Postgres checkpointer is disabled
- `REDIS_URL` empty: Redis client is disabled
- both empty: the backend still works for normal local query, evaluation, and frontend flows

Windows note:

- On Windows, the backend now uses a sync Postgres checkpointer fallback to avoid psycopg async event loop incompatibility.
- A healthy Windows startup should show logs similar to:
  - `LangGraph checkpoint tables ready`
  - `Postgres checkpointer ready (sync fallback)`
- If those logs do not appear, the backend can still start, but Postgres-backed checkpoint persistence is not active in that session.

Useful runtime flags:

- `WORKFLOW_PLANNER_DEBUG_CAPTURE=true`
- `PLANNER_CACHE_TTL_SECONDS=120`
- `PLANNER_CACHE_MAX_ENTRIES=256`

## Typical Local Workflow

1. Upload a document in the `Documents` view.
2. Persist chunks and embeddings, or use one-click pipeline generation.
3. Run a retrieval query in the `Query` view.
4. Run an agent request and inspect the workflow trace.
5. Force a recoverable workflow failure and recover it from the query console.
6. Inspect recovery lineage and chain navigation in recent workflow runs.
7. Run retrieval, route, workflow, or tool-execution evaluation datasets from the `Evaluation` view.
8. Review the persisted latest report, history deltas, and dashboard overview.

## Demo Path

The strongest end-to-end demo path today is:

1. Submit an `agent_v2` ticketing request such as `Create a high severity ticket for payment-service outage`.
2. Inject a persistent ticketing failure with `debug_fault_injection`.
3. Observe the run fail with `retry_exhausted` and structured recovery actions such as `resume_from_failed_step`.
4. Recover the run through the unified recovery entrypoint or the Query UI.
5. Inspect:
   - the recovered run
   - resumed or retried step metadata
   - recovery lineage
   - recovery chain navigation
6. Open `Evaluation` and review benchmark highlights, overview metrics, and saved report history.

For a repeatable walkthrough, use:

- [demo_playbook.md](/d:/project/agent-knowledge-system/docs/demo_playbook.md)
- [demo_recovery_flow.ps1](/d:/project/agent-knowledge-system/scripts/demo_recovery_flow.ps1)

## Qdrant Backfill

For stable local development, start the standalone Qdrant service first:

```powershell
docker compose up -d qdrant
```

Then point the app at the server instead of embedded storage:

```env
QDRANT_URL=http://localhost:6333
QDRANT_LOCAL_PATH=
```

Keep `EMBEDDING_HTTP_TRUST_ENV=false` unless you intentionally rely on a
working system proxy for outbound model requests.

After enabling `VECTOR_STORE_PROVIDER=qdrant` and configuring either
`QDRANT_LOCAL_PATH` or `QDRANT_URL`, you can batch-sync all persisted
embedding artifacts into Qdrant:

```powershell
cd backend
.\.venv\Scripts\activate
python ..\scripts\backfill_qdrant.py
```

## External Knowledge Validation

External datasets are staged under `data/external`.

The current small-batch validation path imports 10 records from each selected
dataset, persists chunks and Gemini embeddings, syncs them into Qdrant, and
then runs representative retrieval smoke tests:

```powershell
cd backend
.\.venv\Scripts\python ..\scripts\import_external_knowledge_assets.py --input ..\data\external\processed\customer_support_tickets.normalized.json --limit 10
.\.venv\Scripts\python ..\scripts\import_external_knowledge_assets.py --input ..\data\external\processed\it_support_v2.normalized.json --limit 10
.\.venv\Scripts\python ..\scripts\import_external_knowledge_assets.py --input ..\data\external\processed\bugsrepo_structured.normalized.json --limit 10

.\.venv\Scripts\python ..\scripts\persist_external_knowledge_assets.py --input ..\data\external\processed\customer_support_tickets.normalized.json --limit 10
.\.venv\Scripts\python ..\scripts\persist_external_knowledge_assets.py --input ..\data\external\processed\it_support_v2.normalized.json --limit 10
.\.venv\Scripts\python ..\scripts\persist_external_knowledge_assets.py --input ..\data\external\processed\bugsrepo_structured.normalized.json --limit 10

.\.venv\Scripts\python ..\scripts\validate_external_knowledge_retrieval.py --strict
```

Expected validation state:

- Qdrant collection `agent_knowledge_chunks`
- vector size `3072`
- external retrieval smoke cases pass for:
  - `customer_support_tickets`
  - `it_support_v2`
  - `bugsrepo_structured`

## Retrieval Eval Matrix

You can benchmark one or more retrieval datasets against a specific vector
store provider without editing `.env` between runs:

```powershell
backend\.venv\Scripts\python scripts\run_retrieval_eval.py --all-datasets --provider qdrant --provider llamaindex --top-k 3 --persist
```

If a dataset has not been indexed for the selected provider yet, the script
records that dataset in the `failures` list instead of aborting the whole run.

## Testing

### Backend

```powershell
cd backend
.\.venv\Scripts\activate
$env:PYTHONPATH='.'
pytest
```

### Frontend

```powershell
cd frontend
npm test
npm run build
```

## Project Structure

- `backend/`: FastAPI backend and agent runtime
- `frontend/`: React console
- `data/`: local raw documents, chunks, embeddings, eval datasets, and tool state
- `docs/`: architecture and planning notes
- `scripts/`: helper scripts for local development and evaluation

## Current Focus

The next iteration focus is runtime maturity and project hardening rather than feature sprawl:

- tighter benchmark and metrics packaging
- stronger project documentation and demo clarity
- more realistic adapter boundaries
- broader evaluation coverage
- deeper corpus-native retrieval over time
- deeper runtime policy and analytics over time
