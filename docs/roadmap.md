# Roadmap

## Phase 1: Foundation
Goal: establish a runnable local development skeleton.

Tasks:
- initialize repository structure
- set up FastAPI backend
- set up React frontend
- define project configuration
- create upload and query API placeholders

Status:
- completed

## Phase 2: Document Pipeline
Goal: build the first end-to-end document processing flow.

Tasks:
- implement document upload
- save files locally
- extract text from documents
- perform chunking
- generate embeddings
- build FAISS index

Status:
- ingestion completed for `.txt` and `.md`
- persisted chunks completed
- persisted embeddings completed
- document deletion with artifact cleanup completed
- FAISS index not implemented yet

## Phase 3: Basic RAG
Goal: support retrieval-augmented question answering.

Tasks:
- implement vector retrieval
- add keyword retrieval
- build hybrid retrieval
- connect LLM API
- return answers with source context

Status:
- retrieval completed
- diagnostics completed
- Gemini/OpenAI chat integration completed
- lightweight reranking completed
- retrieval evaluation datasets and benchmark API completed
- hybrid retrieval not implemented yet

## Phase 4: Agent and Tools
Goal: turn the RAG system into a task-execution agent.

Tasks:
- add request router
- add tool calling logic
- support structured task outputs
- build basic agent workflow

Status:
- not started as a runnable workflow layer
- benchmark content and architecture direction are prepared

## Phase 5: Evaluation and Optimization
Goal: make the system measurable and improvable.

Tasks:
- add benchmark dataset
- evaluate retrieval quality
- track latency and token usage
- add trace logging
- optimize context construction

Status:
- retrieval benchmarks completed
- latency and provider tracing completed
- frontend evaluation console completed
- deeper observability and cost tracking not implemented yet

## Near-Term Next Steps

- add frontend routing and deeper component polish
- expand evaluation datasets beyond the current two curated documents
- add vector index storage beyond local JSON artifacts
- start the first agent workflow and tool execution path
