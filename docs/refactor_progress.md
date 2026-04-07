# LangGraph 重构进度

重构目标：用 LangGraph + LlamaIndex + Postgres/Redis 替换现有手工编排层，保留 FastAPI + React 外壳。

## 技术栈变更

| 层级 | 旧实现 | 新实现 |
|------|--------|--------|
| 编排/状态机 | `orchestrator_service.py`（手写，3500行） | LangGraph `StateGraph` |
| 路由决策 | 正则匹配 `router_service.py` | LLM Native Function Calling |
| 持久化 | JSON 文件 `state_store.py` | LangGraph `AsyncPostgresSaver` |
| 会话缓存 | 无 | Redis |
| RAG/检索 | 自研 FAISS + 手写 reranker | LlamaIndex |
| 工具协议 | 自研 adapter | MCP |
| 可观测性 | 自研评估框架 | LangSmith + 保留评估框架 |

---

## 分包计划

### Phase 0：基础设施

- [x] **Package 0** — Docker Compose（Postgres 16 + Redis 7）+ requirements 基础依赖
  - 新增：`docker-compose.yml`、`scripts/verify_infra.py`
  - Commit：`chore: add infrastructure foundation for LangGraph refactor`

- [x] **Package 1** — 安装 LangGraph 生态依赖
  - 新增：`langgraph>=0.2`、`langgraph-checkpoint-postgres`、`langsmith`、`psycopg[binary]`
  - 验证：181 tests passed
  - Commit：`chore: add LangGraph, checkpoint-postgres, and langsmith dependencies`

---

### Phase 1：替换持久化层

- [x] **Package 2** — LangGraph `AsyncPostgresSaver` 初始化
  - 新增：`storage/db/checkpoint.py`（autocommit setup + pool + lifespan）
  - 更新：`main.py` 加入 FastAPI lifespan，`app.state.checkpointer` 挂载
  - Postgres 自动创建 4 张 checkpoint 表（checkpoints / blobs / writes / migrations）
  - 验证：181 tests passed，DATABASE_URL 为空时优雅降级
  - Commit：`feat: init AsyncPostgresSaver in FastAPI lifespan (Package 2)`

- [x] **Package 3** — Redis 客户端基础设施
  - 新增：`storage/cache/redis_client.py`（async client + lifespan）
  - 更新：`main.py` lifespan 嵌套挂载 `app.state.redis`
  - planner cache 暂保持内存实现（Phase 3 重写时整体替换）
  - 验证：181 tests passed，REDIS_URL 为空时优雅降级
  - Commit：`feat: add Redis async client to FastAPI lifespan (Package 3)`

---

### Phase 2：LlamaIndex 接管 RAG

- [x] **Package 4** — 安装 LlamaIndex 依赖 + 验证导入
  - 新增：`llama-index-core`、`llama-index-embeddings-openai`、`llama-index-embeddings-google`
  - pgvector 暂缓（Docker 镜像网络问题），改用 `SimpleVectorStore` 文件持久化
  - 验证：181 tests passed
  - Commit：`chore: add LlamaIndex dependencies (Package 4)`

- [x] **Package 5** — LlamaIndex `IngestionPipeline` 并行接入
  - 新增：`services/ingestion/llamaindex_ingestion_service.py`（自定义 Embedding 适配器 + build/load/query）
  - 更新：`persist_embeddings` 路由在原有 JSON pipeline 后额外构建 LlamaIndex 索引
  - 新增：`tests/test_llamaindex_ingestion.py`（5 个测试）
  - 验证：186 tests passed
  - Commit：`feat: add LlamaIndex ingestion pipeline alongside existing embedding service`
- [x] **Package 6** — LlamaIndex 检索替换手写余弦相似度
  - 新增：`services/retrieval/llamaindex_retrieval_service.py`（适配 RetrievalResult schema，索引不存在时抛 FileNotFoundError）
  - 更新：`query_service.py` 优先用 LlamaIndex，回退到旧余弦相似度
  - 新增：`tests/test_llamaindex_retrieval.py`（5 个测试，覆盖回退逻辑）
  - 验证：191 tests passed
  - Commit：`feat: switch query path to LlamaIndex retrieval with legacy fallback`
- [ ] **Package 6.5** — 切换 pgvector（网络恢复后）

---

### Phase 3：LangGraph 替换 Orchestrator（核心）

- [x] **Package 7** — 定义 `AgentState` 和基础 Graph 骨架
  - 新增：`services/agent_v2/state.py`（AgentState TypedDict，含 messages channel）
  - 新增：`services/agent_v2/graph.py`（StateGraph，5 个节点，条件路由）
  - 新增：`services/agent_v2/nodes/`（router / retrieval / tool_exec / clarify / answer，均为 stub）
  - 新增：`tests/test_agent_v2_graph.py`（5 个测试，覆盖三条路径）
  - 验证：196 tests passed
  - Commit：`feat: add LangGraph AgentState and graph skeleton with stub nodes`
- [x] **Package 8** — LLM Function Calling 替换正则路由
  - 新增：`services/llm/route_planner_service.py`（LLM-first route planner，含 OpenAI / Gemini provider、缓存与 fallback）
  - 更新：`services/agent_v2/nodes/router.py` 接入 LLM route decision，失败时回退旧 `router_service`
  - 更新：`services/agent_v2/state.py` 增加 `route_reason`、`route_planning_mode`
  - 新增：`tests/test_route_planner_service.py`、`tests/test_agent_v2_router_node.py`
  - 验证：205 tests passed
  - Commit：`feat: add llm-backed router node for agent_v2 graph`
- [x] **Package 8.5** — 暴露 `agent_v2` 独立执行入口
  - 新增：`services/agent_v2/query_service.py`（调用 graph 并适配 `AgentWorkflowResponse`）
  - 更新：`api/routes/query.py` 新增 `/api/query/agent-v2`
  - 新增：`tests/test_agent_v2_api.py`、`tests/test_agent_v2_query_service.py`
  - 验证：209 tests passed
  - Commit：`feat: expose agent_v2 execution path behind separate api route`
- [x] **Package 9** — 工具节点迁移（ticketing / system_status / document_search）
  - 更新：`services/agent_v2/nodes/tool_exec.py` 接入现有 tool planner 和 executor
  - 更新：`services/agent_v2/query_service.py` 透传 `tool_plan` / `tool_execution`
  - 新增：`tests/test_agent_v2_tool_node.py`，并扩展 `tests/test_agent_v2_query_service.py`
  - 验证：212 tests passed
  - Commit：`feat: wire existing tool execution into agent_v2 tool node`
- [x] **Package 9.5** — LlamaIndex 检索和 answer 节点接入
  - 更新：`services/agent_v2/nodes/retrieval.py` 在 graph 内直接调用 `run_query()`
  - 更新：`services/agent_v2/query_service.py` 直接从 `final_state` 对接 retrieval / answer metadata
  - 更新：`services/agent_v2/state.py` 增加 answer metadata 字段
  - 新增：`tests/test_agent_v2_retrieval_node.py`，并更新 graph / query service 测试
  - 验证：214 tests passed
  - Commit：`feat: connect llamaindex retrieval and answer nodes in agent_v2`
- [x] **Package 10** — 恢复逻辑迁移（Checkpointer 自动处理 resume）
  - 新增：`services/agent_v2/run_store.py`，独立持久化 `agent_v2` workflow runs
  - 更新：`services/agent_v2/query_service.py` 持久化每次运行结果，并支持基于 checkpoint 的最小 resume
  - 更新：`api/routes/query.py` 新增 `/api/query/agent-v2/resume`、`/api/query/agent-v2/runs`、`/api/query/agent-v2/runs/{run_id}`
  - 新增：`tests/test_agent_v2_run_store.py`，并扩展 `tests/test_agent_v2_api.py` / `tests/test_agent_v2_query_service.py`
  - 验证：220 tests passed
  - Commit：`feat: add checkpoint-backed run persistence and resume for agent_v2`
- [x] **Package 11** — 澄清节点（LangGraph `interrupt()` 替换 clarification_service）
  - 更新：`services/agent_v2/nodes/clarify.py` 使用 `interrupt()` 发起澄清，并在 resume 后重写请求
  - 更新：`services/agent_v2/graph.py` 将 `clarify -> END` 改为 `clarify -> router`，支持澄清后继续执行
  - 更新：`services/agent_v2/query_service.py` 识别 interrupt 响应，并支持 `Command(resume=clarification_context)`
  - 更新：`api/routes/query.py` 将 `clarification_context` 透传到 `/api/query/agent-v2/resume`
  - 更新：`services/agent_v2/state.py` 增加 `clarification_plan` / `applied_clarification_fields` / `question_rewritten`
  - 新增/更新：graph、query service、API、router、tool、retrieval 测试
  - 验证：222 tests passed
  - Commit：`feat: migrate clarification flow to langgraph interrupt`

---

### Phase 4：Streaming + Tracing

- [x] **Package 12** — LangSmith tracing 接入
  - 新增：`services/agent_v2/tracing.py`，统一封装 LangSmith client、trace context、trace finalize
  - 更新：`services/agent_v2/query_service.py` 在 orchestrate / resume 外层增加 tracing，记录输入、关键 metadata 和结果摘要
  - 更新：`app/core/config.py`、`.env.example` 增加 `LANGSMITH_TRACING_ENABLED / LANGSMITH_API_KEY / LANGSMITH_PROJECT / LANGSMITH_ENDPOINT`
  - 新增：`tests/test_agent_v2_tracing.py`，并扩展 `tests/test_agent_v2_query_service.py`
  - 验证：225 tests passed
  - Commit：`feat: add langsmith tracing for agent_v2 runtime`
- [ ] **Package 13** — FastAPI SSE streaming，前端实时展示 Agent 思考过程

---

### Phase 5：Multi-Agent（按需）

- [ ] **Package 14** — Supervisor + 专门子 Agent 拆分

---

## 当前状态

**进行中**：Phase 3（LangGraph 替换 Orchestrator）。

- 已完成：Package 7，LangGraph `AgentState` + graph skeleton 已落地
- 已完成：Package 8，`agent_v2` router 已切换为 LLM-first + legacy fallback
- 已完成：Package 8.5，`agent_v2` 已可通过独立 API 路径调用
- 已完成：Package 9，`agent_v2` 工具路径已执行 ticketing / system_status
- 已完成：Package 9.5，`agent_v2` knowledge retrieval 已直接运行检索 + answer pipeline
- 已完成：Package 10，`agent_v2` 已支持 run 持久化、查询和 checkpoint resume 骨架
- 已完成：Package 11，`agent_v2` 已支持 clarification interrupt 与 resume 后继续执行
- 当前下一步：Phase 4 / Package 13（FastAPI SSE streaming）
- 测试基线：225 tests passed，0 failed

## 测试基线

| 时间 | 通过 | 失败 | 备注 |
|------|------|------|------|
| 重构启动前 | 181 | 0 | 基线 |
| Package 1 后 | 181 | 0 | LangGraph 依赖不影响现有测试 |
| Package 2 后 | 181 | 0 | FastAPI lifespan + checkpointer 不影响现有测试 |
| Package 3 后 | 181 | 0 | Redis client 不影响现有测试 |
| Package 4 后 | 181 | 0 | LlamaIndex 依赖不影响现有测试 |
| Package 5 后 | 186 | 0 | 新增 5 个 LlamaIndex ingestion 测试 |
| Package 6 后 | 191 | 0 | 新增 5 个 LlamaIndex retrieval 测试 |
| Package 7 后 | 196 | 0 | 新增 5 个 LangGraph graph 测试 |
| Package 8 后 | 205 | 0 | 新增 route planner 与 router node 测试 |
| Package 8.5 后 | 209 | 0 | 新增 agent_v2 API 与 query service 测试 |
| Package 9 后 | 212 | 0 | 新增 tool node 测试，工具路径打通 |
| Package 9.5 后 | 214 | 0 | 新增 retrieval node 测试，agent_v2 检索路径打通 |
| Package 10 后 | 220 | 0 | 新增 run store / resume API 测试，agent_v2 持久化链路打通 |
| Package 11 后 | 222 | 0 | 新增 clarification interrupt / resume 测试，澄清后继续执行打通 |
