# Agent Knowledge System

A local-first agent runtime for engineering and operations scenarios — document-backed knowledge retrieval, LLM-routed tool execution, multi-step workflow orchestration, and persisted run recovery.

---

## Quick Start

**Prerequisites:** Docker Desktop running, Python venv ready, Node installed.

```powershell
# 1. Start infrastructure
docker compose up -d
docker compose ps   # wait until aks_qdrant / aks_postgres / aks_redis are healthy

# 2. Backend (new terminal)
cd backend
.\.venv\Scripts\activate
$env:PYTHONPATH = '.'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 3. Frontend (new terminal)
cd frontend
npm run dev
```

| Service | URL |
|---------|-----|
| Backend API | `http://127.0.0.1:8000` |
| OpenAPI docs | `http://127.0.0.1:8000/docs` |
| Frontend console | `http://127.0.0.1:5173` |

**Healthy startup signs** (backend logs):
```
LangGraph checkpoint tables ready
Postgres checkpointer ready (sync fallback)
Redis client ready
Application startup complete.
```

### First-time setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

cd ../frontend
npm install
```

### Minimal mode (no Docker)

Leave `DATABASE_URL` and `REDIS_URL` empty in `.env`. The backend still works for query, retrieval, and frontend flows — checkpoint persistence and Redis are disabled.

---

## What This Is

An **Agentic Platform** built on LangGraph. The infrastructure is production-quality; the tool adapters are currently local mocks.

**Routing:** Incoming requests are classified by an LLM router into one of three paths — knowledge retrieval, tool/workflow execution, or clarification.

**Two active workflows:**

- **Incident Triage** — service health check → runbook evidence search → ticket draft → human confirmation → submit
- **Service Runtime Review** — service health check → dependency inspection → runbook guidance

**What it has:**
- LangGraph orchestration with checkpoint-backed resume and clarification interrupts
- Qdrant-backed vector retrieval (primary), section-aware chunking, grounded answers with citations
- 4 local tool adapters: `system_status`, `document_search`, `service_dependencies`, `ticketing`
- Persisted workflow runs with trace events, lineage metadata, and recovery semantics
- Evaluation framework for retrieval, routing, workflow, and tool-execution benchmarks
- SSE streaming to the frontend query console

**What it doesn't have yet:**
- Real external tool integrations (all adapters are mock/local)
- LLM-driven skill dispatch (currently regex-pattern-based)
- Inner agent loop (ReAct) — workflow steps are deterministic sequences

---

## Architecture

```
Request
  │
  ▼
router_node          ← LLM classifies: retrieval / tool_execution / clarification
  │
  ▼
supervisor_node      ← selects knowledge_specialist or operations_specialist
  │
  ├─▶ knowledge_specialist
  │     retrieval_node → answer_node
  │
  ├─▶ operations_specialist
  │     tool_exec_node → answer_node
  │       ├─ incident_triage workflow (4 steps)
  │       ├─ service_runtime_review workflow (3 steps)
  │       └─ single-step LLM tool plan
  │
  └─▶ clarification_specialist
        clarify_node (interrupt) → router_node
```

State persisted via LangGraph (PostgreSQL checkpointer) + JSON run store.

---

## Key Workflows

### Incident Triage

```
"Check payment-service in production for timeout issues and prepare a high severity ticket draft"
```

1. `system_status:query` — inspect service health
2. `document_search:query` — search service runbook for symptom evidence
3. `document_search:query` — retrieve external support records from Qdrant
4. `ticketing:draft` — prepare incident ticket draft
5. Human confirmation (clarification interrupt)
6. `ticketing:submit` — submit only after explicit approval

### Service Runtime Review

```
"Check payment-service in production status and tell me what to look at for timeout issues"
```

1. `system_status:query` — inspect service health and active alerts
2. `service_dependencies:query` — identify likely downstream dependency issues
3. `document_search:query` — pull runbook guidance for the symptom

---

## Configuration

Copy `.env.example` to `.env` at the repo root.

### Standard (Gemini + Docker)

```env
AGENT_DEFAULT_RUNTIME=v2
EMBEDDING_PROVIDER=gemini
CHAT_PROVIDER=gemini
ROUTE_PLANNER_PROVIDER=gemini
TOOL_PLANNER_PROVIDER=gemini
CLARIFICATION_PLANNER_PROVIDER=gemini
WORKFLOW_PLANNER_PROVIDER=gemini

GEMINI_API_KEY=your_key
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GEMINI_CHAT_MODEL=gemini-2.5-flash-lite

DATABASE_URL=postgresql://postgres:password@127.0.0.1:5432/agent_knowledge_system
REDIS_URL=redis://127.0.0.1:6379/0
QDRANT_URL=http://127.0.0.1:6333
KNOWLEDGE_WRITE_QDRANT=true
```

### Minimal (no LLM, no Docker)

```env
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

### Key knobs

| Variable | Default | Notes |
|----------|---------|-------|
| `AGENT_DEFAULT_RUNTIME` | `legacy` | Set to `v2` for the active runtime |
| `QDRANT_URL` | — | Use for local or remote Qdrant server |
| `QDRANT_LOCAL_PATH` | — | Embedded mode; relative paths resolve from repo root |
| `KNOWLEDGE_WRITE_QDRANT` | `true` | Write embeddings to Qdrant on persist |
| `WORKFLOW_PLANNER_DEBUG_CAPTURE` | `false` | Capture planner prompts/responses |
| `PLANNER_CACHE_TTL_SECONDS` | `120` | LLM planner response cache TTL |

> **Windows note:** The backend uses a sync Postgres checkpointer fallback to avoid psycopg async event loop issues. Behavior is identical; look for `Postgres checkpointer ready (sync fallback)` in logs.

---

## Recovery Model

| Recovery action | When to use |
|----------------|-------------|
| `resume_with_clarification` | Workflow paused waiting for user input |
| `resume_from_failed_step` | Tool step failed; reuse completed steps, retry from failure point |
| `manual_retrigger` | Restart the full workflow as a new run |

Recovery chains are persisted with `root_run_id`, `source_run_id`, `recovery_depth`, and `recovered_via_action`.

---

## API Reference

### Health

```
GET  /api/health
GET  /api/health/system
```

### Documents

```
GET    /api/documents
POST   /api/documents/upload
GET    /api/documents/{filename}
DELETE /api/documents/{filename}
GET    /api/documents/{filename}/assets
GET    /api/documents/{filename}/chunks
POST   /api/documents/{filename}/chunks/persist
GET    /api/documents/{filename}/chunks/persisted
POST   /api/documents/{filename}/embeddings/persist
GET    /api/documents/{filename}/embeddings/persisted
```

### Agent (default surface — routes to v2 when `AGENT_DEFAULT_RUNTIME=v2`)

```
POST /api/query/agent
POST /api/query/agent/resume
POST /api/query/agent/recover
GET  /api/query/agent/runs
GET  /api/query/agent/runs/{run_id}
```

### Agent v2 (explicit surface)

```
POST /api/query/agent-v2
POST /api/query/agent-v2/stream
POST /api/query/agent-v2/resume
POST /api/query/agent-v2/recover
GET  /api/query/agent-v2/runs
GET  /api/query/agent-v2/runs/{run_id}
```

### Query utilities

```
POST /api/query
POST /api/query/route
POST /api/query/diagnostics
GET  /api/query/tools
POST /api/query/tools/plan
POST /api/query/tools/execute
```

### Run maintenance (legacy control plane)

```
POST /api/query/agent/runs/migrate
GET  /api/query/agent/runs/stats
POST /api/query/agent/runs/prune
POST /api/query/agent/runs/reset
```

### Evaluation

```
GET  /api/evaluation/overview
GET  /api/evaluation/metrics-summary
GET  /api/evaluation/retrieval/datasets
POST /api/evaluation/retrieval
GET  /api/evaluation/retrieval/latest
GET  /api/evaluation/retrieval/history
GET  /api/evaluation/agent-route/datasets
POST /api/evaluation/agent-route
GET  /api/evaluation/agent-route/latest
GET  /api/evaluation/agent-route/history
GET  /api/evaluation/agent-workflow/datasets
POST /api/evaluation/agent-workflow
GET  /api/evaluation/agent-workflow/latest
GET  /api/evaluation/agent-workflow/history
GET  /api/evaluation/agent-tool-execution/datasets
POST /api/evaluation/agent-tool-execution
GET  /api/evaluation/agent-tool-execution/latest
GET  /api/evaluation/agent-tool-execution/history
```

---

## Testing

```powershell
# Backend
cd backend
.\.venv\Scripts\activate
$env:PYTHONPATH = '.'
pytest

# Frontend
cd frontend
npm test
npm run build
```

---

## Utilities

### Backfill Qdrant from persisted embeddings

```powershell
cd backend
.\.venv\Scripts\activate
python ..\scripts\backfill_qdrant.py
```

### Import external knowledge assets

```powershell
cd backend
.\.venv\Scripts\python ..\scripts\import_external_knowledge_assets.py --input ..\data\external\processed\customer_support_tickets.normalized.json --limit 10
.\.venv\Scripts\python ..\scripts\persist_external_knowledge_assets.py --input ..\data\external\processed\customer_support_tickets.normalized.json --limit 10
.\.venv\Scripts\python ..\scripts\validate_external_knowledge_retrieval.py --strict
```

---

## Project Structure

```
backend/    FastAPI backend, agent runtime, services
frontend/   React + Vite console
data/       Documents, chunks, embeddings, eval datasets, tool state, mock data
docs/       Architecture notes and planning
scripts/    Dev and evaluation helper scripts
```

## Tech Stack

- **Backend:** FastAPI, Python
- **Agent runtime:** LangGraph (orchestration, checkpoints, interrupts)
- **Retrieval:** Qdrant (primary vector store), section-aware chunking, grounded citations
- **LLM:** Gemini / OpenAI APIs, with local fallback planners
- **Persistence:** PostgreSQL (LangGraph checkpoints), JSON files (run store, tool state)
- **Cache:** Redis
- **Observability:** LangSmith tracing, persisted evaluation reports
- **Frontend:** React, Vite
