# Agent Knowledge System

A local-first AI engineering project for building an enterprise knowledge base and task-execution agent system.

## Overview

This project aims to build an agent-based knowledge system that supports:

- multi-source document ingestion
- document parsing and chunking
- retrieval-augmented generation (RAG)
- tool calling for task execution
- evaluation and observability

The current implementation is already beyond repository scaffolding. The system now includes:

- local document upload and preview for `.txt` and `.md`
- persisted chunk and embedding artifacts
- Gemini and OpenAI provider routing with local fallback paths
- retrieval diagnostics and lightweight reranking
- retrieval evaluation datasets and benchmark APIs
- a React console for documents, query tracing, and evaluation workflows

## Tech Stack

- Backend: FastAPI
- Frontend: React + Vite
- Database: PostgreSQL
- Cache: Redis
- Vector Index: FAISS
- LLM: API-based models

## Current Stage

Phase 1, Phase 2, and Phase 3 are complete.

Current focus:

- stable ingestion and indexing workflow
- retrieval quality diagnostics
- agent workflow runtime and maintenance semantics
- evaluation and observability
- frontend console polish

## Implemented Capabilities

### Backend

- `GET /api/health`
- `GET /api/health/system`
- `GET /api/documents`
- `GET /api/documents/{filename}`
- `POST /api/documents/upload`
- `DELETE /api/documents/{filename}`
- `GET /api/documents/{filename}/chunks`
- `POST /api/documents/{filename}/chunks/persist`
- `GET /api/documents/{filename}/chunks/persisted`
- `POST /api/documents/{filename}/embeddings/persist`
- `GET /api/documents/{filename}/embeddings/persisted`
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
- `GET /api/query/tools`
- `POST /api/query/tools/plan`
- `POST /api/query/tools/execute`
- `GET /api/evaluation/retrieval/datasets`
- `POST /api/evaluation/retrieval`

### Agent Workflow Runtime

- structured workflow runs with step-level metadata
- terminal reasons, failure semantics, and resume semantics
- persisted workflow run summaries and legacy migration support
- workflow run maintenance endpoints for stats, pruning, and reset

### Frontend Console

- `Documents`
  - upload documents
  - preview content
  - persist chunks
  - persist embeddings
  - one-click pipeline generation
  - delete document with artifact cleanup
- `Query Lab`
  - run retrieval-backed queries
  - inspect answer tracing
  - inspect diagnostics candidates and rerank scores
- `Evaluation`
  - list retrieval datasets
  - run benchmark reports
  - inspect hit/miss cases

## Local Setup

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend URLs:

- API root: `http://127.0.0.1:8000/`
- Swagger: `http://127.0.0.1:8000/docs`

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend URL:

- Console: `http://127.0.0.1:5173`

The frontend proxies `/api` requests to the local FastAPI server by default.

## Environment Configuration

Create a repo-root `.env` file based on `.env.example`.

Common provider configuration:

```env
EMBEDDING_PROVIDER=gemini
CHAT_PROVIDER=gemini

GEMINI_API_KEY=your_key
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GEMINI_CHAT_MODEL=gemini-2.5-flash-lite

OPENAI_API_KEY=
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-4o-mini
```

## Testing

### Backend

```powershell
cd backend
.\.venv\Scripts\pytest
```

### Frontend

```powershell
cd frontend
npm test
npm run build
```

## Example Workflow

1. Upload a document in the `Documents` page.
2. Click `Generate Pipeline` to persist chunks and embeddings.
3. Open `Query Lab` and run a question against the uploaded document.
4. Inspect answer tracing and diagnostics candidates.
5. Open `Evaluation` and run a retrieval benchmark dataset.

## Project Structure

- `backend/`: FastAPI backend
- `frontend/`: React frontend
- `docs/`: architecture and roadmap
- `data/`: raw and processed files
- `scripts/`: helper scripts

## Current Retrieval Evaluation Baseline

The project currently includes two focused benchmark datasets:

- `rag_overview_retrieval_eval.json`
- `agent_workflow_retrieval_eval.json`

With the current pipeline:

- paragraph-aware chunking
- Gemini embeddings
- lightweight heuristic reranking

the local retrieval benchmark currently reaches a strong baseline on both datasets.
