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

- [ ] **Package 7** — 定义 `AgentState` 和基础 Graph 骨架
- [ ] **Package 8** — LLM Function Calling 替换正则路由
- [ ] **Package 9** — 工具节点迁移（ticketing / system_status / document_search）
- [ ] **Package 10** — 恢复逻辑迁移（Checkpointer 自动处理 resume）
- [ ] **Package 11** — 澄清节点（LangGraph `interrupt()` 替换 clarification_service）

---

### Phase 4：Streaming + Tracing

- [ ] **Package 12** — LangSmith tracing 接入
- [ ] **Package 13** — FastAPI SSE streaming，前端实时展示 Agent 思考过程

---

### Phase 5：Multi-Agent（按需）

- [ ] **Package 14** — Supervisor + 专门子 Agent 拆分

---

## 当前状态

**进行中**：Phase 2 完成，准备进入 Phase 3（LangGraph 替换 Orchestrator）。

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
