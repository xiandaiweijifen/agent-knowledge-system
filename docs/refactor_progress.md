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

- [ ] **Package 3** — Redis 会话缓存接入
  - 目标：planner cache 从内存改为 Redis
  - 影响文件：`services/llm/planner_cache_service.py`

---

### Phase 2：LlamaIndex 接管 RAG

- [ ] **Package 4** — LlamaIndex `IngestionPipeline` 替换 chunker + text_extractor
- [ ] **Package 5** — LlamaIndex `VectorStoreIndex` + pgvector 替换 FAISS 本地文件
- [ ] **Package 6** — 把 LlamaIndex `QueryEngine` 包成 LangGraph `ToolNode`

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

**进行中**：Package 2 完成，准备进入 Package 3（Redis planner cache）。

## 测试基线

| 时间 | 通过 | 失败 | 备注 |
|------|------|------|------|
| 重构启动前 | 181 | 0 | 基线 |
| Package 1 后 | 181 | 0 | LangGraph 依赖不影响现有测试 |
| Package 2 后 | 181 | 0 | FastAPI lifespan + checkpointer 不影响现有测试 |
