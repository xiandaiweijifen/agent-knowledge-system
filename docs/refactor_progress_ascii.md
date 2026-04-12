# Refactor Progress ASCII Notes

## Package 14.5

- Status: completed
- Commit: `feat: add agent_v2 default-runtime cutover path`
- Added `AGENT_DEFAULT_RUNTIME` with `legacy` default and `v2` opt-in mode.
- When `AGENT_DEFAULT_RUNTIME=v2`, the default `/api/query/agent` entrypoints dispatch to `agent_v2` for:
  - `/api/query/agent`
  - `/api/query/agent/resume` when `run_id` is provided
  - `/api/query/agent/runs`
  - `/api/query/agent/runs/{run_id}`
- Frontend non-stream fallback now calls `/api/query/agent-v2` directly.

## Package 15

- Status: completed
- Commit: `feat: add failed-run semantics and manual retrigger recovery for agent_v2`
- `agent_v2` now persists structured failed runs for tool and retrieval failures.
- Failed tool runs now expose `manual_retrigger` recovery.

- Package 16

- Status: completed
- Commit: `feat: add failed-step resume semantics for agent_v2 recovery`
- Failed single-step tool runs now expose `resume_from_failed_step` and `manual_retrigger`.
- Recovery metadata now includes `resumed_from_step_index` and `retried_step_indices`.

- Package 17

- Status: completed
- Commit: `docs: stabilize runtime docs around agent_v2 default mode`
- README and demo playbook now describe `agent_v2` as the primary runtime target.
- Added explicit notes for `AGENT_DEFAULT_RUNTIME`, default entrypoint behavior, and current recovery boundaries.

## Package 18

- Status: completed
- Commit: `refactor: expose explicit agent_v2 recovery endpoint`
- Added `/api/query/agent-v2/recover` as the explicit recovery surface for `agent_v2`.
- Frontend recovery calls now target the explicit v2 recovery endpoint instead of relying on the legacy compatibility path.

## Package 19

- Status: completed
- Commit: `feat: surface default agent runtime in system health`
- Added `agent_default_runtime` and `default_agent_surface` to `/api/health/system`.
- Frontend system snapshot now shows whether the current default runtime is `legacy` or `agent_v2`.

## Package 20

- Status: completed
- Commit: `refactor: align evaluation overview with agent_v2 run telemetry`
- Evaluation overview now aggregates workflow and recovery metrics from `agent_v2` runs by default.
- Overview falls back to legacy runs only when no `agent_v2` run history is available and the runtime has not been switched to `v2`.
- Workflow overview responses now expose `runtime_source`, and the frontend evaluation panel surfaces that runtime label.

## Package 21

- Status: completed
- Commit: `refactor: migrate agent workflow evaluation dataset to agent_v2 semantics`
- Agent workflow evaluation now executes through `agent_v2` orchestration, resume, and recover entrypoints.
- Workflow evaluation cases now cover `agent_v2`-compatible scenarios: knowledge retrieval, single-step tool execution, clarification resume, failed-step resume, and manual retrigger recovery.
- Workflow eval schema now records recovery action expectations so reports can distinguish plain resume traces from explicit recovery actions.

## Package 22

- Status: completed
- Commit: `refactor: make llamaindex the explicit primary retrieval path`
- Added `KNOWLEDGE_RETRIEVAL_MODE` with `llamaindex`, `auto`, and `legacy` modes.
- Default knowledge queries now require a persisted LlamaIndex index in standard runtime mode.
- Legacy retrieval remains available for migration, debug, and evaluation flows through explicit `auto` or `legacy` mode selection.

## Package 23

- Status: completed
- Commit: `feat: expose document knowledge asset readiness`
- Document list responses now include `knowledge_assets` readiness for persisted chunks, persisted embeddings, and LlamaIndex index state.
- Added `/api/documents/{filename}/assets` for explicit per-document knowledge asset status.
- Document deletion now removes persisted LlamaIndex stores alongside chunk and embedding artifacts.
- Frontend document cards now surface `chunks / embeddings / llamaindex` readiness directly instead of inferring state from 404 responses.

## Package 24

- Status: completed
- Commit: `refactor: limit legacy retrieval to debug and eval modes`
- Standard knowledge query paths now reject `KNOWLEDGE_RETRIEVAL_MODE=auto|legacy` with `knowledge_retrieval_mode_requires_debug_or_eval`.
- `/api/query` and knowledge retrieval inside agent workflows now require explicit LlamaIndex mode in normal runtime operation.
- Legacy retrieval remains available through diagnostics and retrieval evaluation flows as the project baseline/debug path.

## Package 25

- Status: completed
- Commit: `feat: add section-aware chunk metadata for knowledge nodes`
- Chunk records now persist `section_title`, `section_path`, and `heading_level` derived from markdown heading context.
- Embedding records now carry the same section metadata so legacy retrieval artifacts retain document structure.
- LlamaIndex node metadata now includes source suffix plus section metadata, preparing the knowledge layer for metadata-aware retrieval, citation, and multi-file source display.

## Package 26

- Status: completed
- Commit: `feat: add query normalization and metadata-aware retrieval groundwork`
- Knowledge retrieval now normalizes user phrasing before vector lookup so polite prefixes do not fragment retrieval behavior.
- Legacy retrieval scoring now factors section metadata (`section_title` / `section_path`) into lightweight rerank bonuses.
- LlamaIndex retrieval results now surface section metadata through `RetrievedChunkMatch` and apply the same lightweight metadata bonus before final ranking.

## Package 27

- Status: completed
- Commit: `feat: add corpus retrieval groundwork for multi-file knowledge queries`
- `/api/query` now accepts `filename=null` and treats that as a corpus-scoped knowledge query in explicit LlamaIndex mode.
- Added `retrieve_with_llamaindex_corpus()` to aggregate per-document LlamaIndex matches, merge them, and return a unified ranked result set.
- Retrieval responses now expose `retrieval_scope` and `corpus_filenames`, so multi-file knowledge queries have an explicit result contract before full UI support lands.

## Package 28

- Status: completed
- Commit: `feat: surface corpus retrieval scope and source metadata in query view`
- Query results now surface corpus scope, participating corpus documents, and per-match source metadata in the frontend.

## Package 29

- Status: completed
- Commit: `feat: enable corpus queries without document context`
- The Query Lab now allows `Run Query` without a selected document and dispatches corpus retrieval in explicit LlamaIndex mode.

## Package 30

- Status: completed
- Commit: `feat: add lightweight source diversification for corpus retrieval`
- Corpus ranking now applies a light source-level penalty after initial scoring so near-tied results do not let a single document dominate every top-k slot.

## Package 31

- Status: completed
- Commit: `feat: add metadata-aware corpus document filtering`
- Corpus retrieval now narrows candidate documents with lightweight semantic hints such as `runbook`, `incident`, `workflow`, and `overview` before ranking.

## Package 32

- Status: completed
- Commit: `feat: add grounded answer citations and source-aware synthesis`
- Knowledge responses now return structured `answer_citations` and build answer prompts with explicit source file and source section context.

## Package 33

- Status: completed
- Commit: `refactor: align answer citations with answer-content relevance`
- Citation ranking now considers overlap between answer text, chunk content, and section metadata instead of truncating raw retrieval order.

## Package 34

- Status: completed
- Commit: `feat: add structured answer verification signals for grounded responses`
- Query responses now include `groundedness_status`, `citation_coverage`, and related verification notes so grounded answer quality is a first-class signal.

## Package 35

- Status: completed
- Commit: `feat: integrate answer verification signals into retrieval evaluation`
- Retrieval evaluation reports, overview, and metrics summary now distinguish retrieval quality from grounded answer quality with groundedness and citation coverage metrics.

## Package 36

- Status: completed
- Commit: `feat: add document-kind metadata and unify evidence metadata across retrieval and grounding`
- Documents, chunks, embeddings, retrieval matches, and citations now share a normalized `document_kind` such as `runbook`, `incident`, `workflow`, or `overview`.
- Retrieval, citations, and verification now consume a shared evidence metadata layer instead of duplicating filename-only logic.

## Package 37

- Status: completed
- Commit: `feat: push document-kind metadata into diagnostics and retrieval evaluation narrative`
- Legacy retrieval diagnostics now propagate `document_kind` through ranked candidates.
- Retrieval evaluation case results now record `top_document_kind` and `citation_document_kinds`.
- Metrics summary retrieval copy now describes dominant document kinds alongside hit rate, MRR, groundedness, and citation coverage.

## Test Baseline

- Backend: `268 passed, 0 failed`
- Frontend: `17 passed, 0 failed`
