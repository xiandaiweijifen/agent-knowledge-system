# Agent Knowledge System

An engineering-focused agent system for knowledge retrieval, tool execution, workflow orchestration, and runtime observability.

## What This Project Is

This repository is building a local-first agent knowledge system for engineering and operations scenarios.

It is not just a RAG demo and not just a chat endpoint with a few prompts. The target shape is a system with:

- a document-backed knowledge layer
- an agent routing layer
- tool execution through adapter-style interfaces
- multi-step workflow orchestration
- planner fallback and debugability
- persisted runs, resume behavior, and runtime diagnostics

Today, the project already has a working backend, frontend console, local tool adapters, evaluation flows, and a multi-step agent runtime.

## Current State

The repository is in a middle-to-late build phase.

Implemented and usable today:

- document ingestion for local text-style documents
- persisted chunks and embeddings
- retrieval with diagnostics and lightweight reranking
- knowledge query and fallback answer paths
- request routing for retrieval, tool execution, and clarification
- local tool adapters for `document_search`, `system_status`, and `ticketing`
- LLM-backed `tool planner`, `clarification planner`, and `workflow planner`
- fallback behavior when planner calls fail or are unavailable
- multi-step workflows for:
  - `search_then_ticket`
  - `search_then_summarize`
  - `status_then_ticket`
  - `status_then_summarize`
- resume flows for clarification-driven continuation
- persisted workflow runs with trace events, planner metadata, and maintenance endpoints
- retrieval, route, and workflow evaluation datasets with a frontend evaluation console

Still intentionally unfinished:

- richer runtime recovery such as step retry and rerun from step N
- real external system adapters
- a more formal database-backed state layer
- broader workflow branching and policy logic
- deeper cost and latency analytics

## Core Capabilities

### 1. Knowledge Layer

- upload and preview local documents
- persist chunk artifacts
- persist embedding artifacts
- retrieve relevant chunks for a question
- inspect retrieval diagnostics and ranked candidates
- run fallback answering when no live model answer path is configured

### 2. Agent Layer

- route incoming requests into retrieval, tool execution, or clarification
- plan tool execution with either LLM or heuristic fallback
- plan clarification requests with either LLM or heuristic fallback
- plan workflow decomposition with either LLM or heuristic fallback

### 3. Tool Layer

Local adapter-style tools currently include:

- `document_search`
- `system_status`
- `ticketing`

The ticketing tool currently supports:

- `create`
- `update`
- `close`
- `query`
- `list`

### 4. Workflow Runtime

The agent runtime already supports:

- single-step execution
- multi-step workflow traces
- workflow persistence
- resume metadata
- terminal reasons and failure stages
- planner mode, planner count, and planner latency diagnostics
- run listing, lookup, stats, pruning, reset, and schema migration

### 5. Evaluation and Observability

- retrieval evaluation datasets and reports
- agent route evaluation datasets and reports
- agent workflow evaluation datasets and reports
- workflow planner debug capture
- persisted workflow run inspection through API and frontend

## Architecture Snapshot

High-level backend flow:

1. Documents are uploaded and stored locally.
2. Text is chunked and embedding artifacts are persisted.
3. Retrieval services score and rerank candidate chunks.
4. Requests are routed into retrieval, clarification, or tool/workflow execution.
5. Planner services decide tool or workflow behavior, with fallback paths if model planning fails.
6. Workflow runs are persisted with trace events and planner diagnostics.

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
- `GET /api/query/agent/runs`
- `GET /api/query/agent/runs/{run_id}`
- `POST /api/query/agent/runs/migrate`
- `GET /api/query/agent/runs/stats`
- `POST /api/query/agent/runs/prune`
- `POST /api/query/agent/runs/reset`

### Tools

- `GET /api/query/tools`
- `POST /api/query/tools/plan`
- `POST /api/query/tools/execute`

### Evaluation

- `GET /api/evaluation/retrieval/datasets`
- `POST /api/evaluation/retrieval`
- `GET /api/evaluation/agent-route/datasets`
- `POST /api/evaluation/agent-route`
- `GET /api/evaluation/agent-workflow/datasets`
- `POST /api/evaluation/agent-workflow`

## Tech Stack

- Backend: FastAPI
- Frontend: React + Vite
- LLM access: Gemini and OpenAI APIs, with local fallback paths
- Storage today: local files and JSON state
- Optional infra hooks: PostgreSQL and Redis configuration fields exist, but they are not the primary runtime state path yet

## Local Setup

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
$env:PYTHONPATH='.'
uvicorn app.main:app --reload
```

Backend URLs:

- API root: `http://127.0.0.1:8000/`
- OpenAPI docs: `http://127.0.0.1:8000/docs`

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend URL:

- Console: `http://127.0.0.1:5173`

The frontend proxies `/api` requests to the local FastAPI backend by default.

## Environment Configuration

Create a repo-root `.env` file based on `.env.example`.

Minimal local fallback setup:

```env
APP_ENV=development
EMBEDDING_PROVIDER=mock
CHAT_PROVIDER=fallback
TOOL_PLANNER_PROVIDER=fallback
CLARIFICATION_PLANNER_PROVIDER=fallback
WORKFLOW_PLANNER_PROVIDER=fallback
```

Example Gemini/OpenAI setup:

```env
EMBEDDING_PROVIDER=gemini
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

Useful runtime flags:

- `WORKFLOW_PLANNER_DEBUG_CAPTURE=true`
- `PLANNER_CACHE_TTL_SECONDS=120`
- `PLANNER_CACHE_MAX_ENTRIES=256`

## Typical Local Workflow

1. Upload a document in the `Documents` view.
2. Persist chunks and embeddings, or use one-click pipeline generation.
3. Run a retrieval query in the `Query` view.
4. Run an agent request and inspect the workflow trace.
5. Inspect recent workflow runs from the query console.
6. Run retrieval, route, or workflow evaluation datasets from the `Evaluation` view.

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

## Near-Term Direction

The next iteration focus is runtime maturity rather than feature sprawl:

- failure semantics cleanup
- step retry and richer recovery
- stronger resume behavior
- more realistic adapter boundaries
- broader workflow evaluation coverage
