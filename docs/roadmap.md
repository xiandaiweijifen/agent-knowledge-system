# Roadmap

## Phase 1: Foundation
Goal: establish a runnable local development skeleton.

Tasks:
- initialize repository structure
- set up FastAPI backend
- set up React frontend
- define project configuration
- create upload and query API placeholders

## Phase 2: Document Pipeline
Goal: build the first end-to-end document processing flow.

Tasks:
- implement document upload
- save files locally
- extract text from documents
- perform chunking
- generate embeddings
- build FAISS index

## Phase 3: Basic RAG
Goal: support retrieval-augmented question answering.

Tasks:
- implement vector retrieval
- add keyword retrieval
- build hybrid retrieval
- connect LLM API
- return answers with source context

## Phase 4: Agent and Tools
Goal: turn the RAG system into a task-execution agent.

Tasks:
- add request router
- add tool calling logic
- support structured task outputs
- build basic agent workflow

## Phase 5: Evaluation and Optimization
Goal: make the system measurable and improvable.

Tasks:
- add benchmark dataset
- evaluate retrieval quality
- track latency and token usage
- add trace logging
- optimize context construction