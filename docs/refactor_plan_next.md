# Agent Runtime Refactor Plan

本文件用于承接 `docs/refactor_progress.md`，聚焦后续重构执行顺序、每包目标、建议 commit 名称、测试要求与必要手测。

## 执行原则

- 每一包结束后，代码必须保持可运行、可测试、可回退。
- 优先打通 `agent_v2` 主链路，再做 tracing、streaming、MCP、multi-agent。
- 尽量保持现有 API 契约稳定，避免前端被迫同步大改。
- 每一包提交前都要运行相关测试；涉及 UI、interrupt、resume、streaming 时补充手测。

## 重构主线

1. 让 `LangGraph runtime` 真正可执行并接入现有 API。
2. 迁移 `tool / retrieval / recovery / clarification` 到 `agent_v2`。
3. 完成新 runtime 切流，旧 orchestrator 降级为 fallback 或历史兼容路径。
4. 增加 `LangSmith tracing`、`SSE streaming`、`MCP`、`skills`、`multi-agent`。

## Package Plan

### Package 8

目标：
- 用 LLM route decision 替换 `agent_v2` 中的 stub router。
- 保留 deterministic fallback，避免模型不可用时 graph 失效。
- 固定路由输出 schema：
  - `knowledge_retrieval`
  - `tool_execution`
  - `clarification_needed`

建议 commit 名称：
- `feat: add llm-backed router node for agent_v2 graph`

测试要求：
- 新增 `agent_v2` router 单测。
- 跑后端 `pytest` 全量回归。

建议手测：
- 输入纯知识问答，确认走 retrieval。
- 输入工具型请求，确认走 tool。
- 输入模糊请求，确认走 clarify。

### Package 8.5

目标：
- 暴露 `agent_v2` 独立执行入口。
- 建议新增 `/api/query/agent-v2`，或使用 feature flag 在后端切换。
- 新旧运行时并行存在，便于对照验证。

建议 commit 名称：
- `feat: expose agent_v2 execution path behind separate api route`

测试要求：
- 新增 API 测试。
- 跑后端 `pytest` 全量回归。

建议手测：
- 使用 Swagger 或 curl 调用 `agent-v2` 路径。
- 对比新旧 runtime 返回结构是否满足前端要求。

### Package 9

目标：
- 将 `ticketing / system_status / document_search` 接入 `agent_v2` 的 `tool_exec` node。
- 初期允许复用现有 `tool_service`，先不强行引入 MCP。

建议 commit 名称：
- `feat: wire existing tool execution into agent_v2 tool node`

测试要求：
- 新增 `tool_exec` node 单测。
- 跑后端 `pytest` 全量回归。

建议手测：
- `ticket create / query / update`
- `system_status query`
- `document_search query`

### Package 9.5

目标：
- 将 `retrieval` node 接入当前 LlamaIndex 检索链路。
- 将 `answer` node 接入统一回答生成逻辑。
- 让 `knowledge_retrieval` 路径完整走 `agent_v2`。

建议 commit 名称：
- `feat: connect llamaindex retrieval and answer nodes in agent_v2`

测试要求：
- 新增 retrieval path 单测。
- 跑后端 `pytest` 全量回归。

建议手测：
- 选取已有文档提问。
- 验证返回检索内容、答案、状态字段是否合理。

### Package 10

目标：
- 将 run persistence / resume / lineage 接入 LangGraph checkpointer。
- 优先实现“新图可恢复”，再逐步补齐旧 orchestrator 的全部恢复语义。
- 扩展 `AgentState`，逐步与现有 `AgentWorkflowResponse` 对齐。

建议 commit 名称：
- `feat: add checkpoint-backed run persistence and resume for agent_v2`

测试要求：
- 新增 resume / recovery 单测。
- 跑后端 `pytest` 全量回归。

建议手测：
- 人工触发失败或暂停。
- 验证可以 resume。
- 验证 run 查询、lineage 展示、状态流转正常。

### Package 11

目标：
- 用 LangGraph `interrupt()` 替换现有 clarification 逻辑。
- 支持 clarification pause + resume。
- 前端优先复用现有 clarification UI。

建议 commit 名称：
- `feat: migrate clarification flow to langgraph interrupt`

测试要求：
- 新增 clarification path 单测。
- 跑后端 `pytest` 全量回归。

建议手测：
- 输入歧义请求。
- 验证系统返回 clarification。
- 提交澄清信息后恢复执行。

### Package 11.5

目标：
- 将默认 `/api/query/agent` 切换到 `agent_v2`。
- 保留旧 orchestrator 作为 fallback、debug path 或历史兼容路径。

建议 commit 名称：
- `feat: switch default agent endpoint to agent_v2 runtime`

测试要求：
- 跑后端 `pytest` 全量回归。
- 跑前端 `npm test`。

建议手测：
- 从前端完整走一遍 agent 主流程。
- 检查 recent runs、clarification、resume、recovery。

### Package 12

目标：
- 接入 LangSmith tracing。
- 保留现有 evaluation 框架，不替换。

建议 commit 名称：
- `feat: add langsmith tracing for agent_v2 runtime`

测试要求：
- tracing 配置与开关测试。
- 跑后端 `pytest` 全量回归。

建议手测：
- 配置 LangSmith key。
- 触发一次 agent run。
- 确认 trace 可见。

### Package 13

目标：
- 增加 FastAPI SSE streaming。
- 前端实时展示 route、retrieval、tool、completion 等安全执行事件。
- 不展示不可控的原始思维链。

建议 commit 名称：
- `feat: add sse streaming for agent_v2 execution events`

测试要求：
- SSE 接口测试。
- 跑前端 `npm test`。
- 必要时补充组件测试。

建议手测：
- 发起一次 agent 请求。
- 观察前端是否按事件流实时刷新。

### Package 14

目标：
- 引入 MCP-compatible tool boundary。
- 先兼容现有工具，不强依赖真实外部 MCP server。

建议 commit 名称：
- `feat: add mcp-compatible tool boundary for agent runtime`

测试要求：
- tool contract 测试。
- 跑后端 `pytest` 全量回归。

建议手测：
- 工具发现。
- 工具调用。
- 错误处理和降级。

### Package 15

目标：
- 增加 skill registry。
- 将 `retrieval / incident triage / ticketing / summary` 封装成 skill 级能力单元。

建议 commit 名称：
- `feat: introduce skill registry for reusable agent capabilities`

测试要求：
- skill registry 单测。
- 路由到 skill 的集成测试。
- 跑后端 `pytest` 全量回归。

建议手测：
- 同类请求稳定命中对应 skill。
- skill 的输入输出结构稳定。

### Package 16

目标：
- 增加 supervisor + sub-agent。
- 只拆最有价值的 2 到 3 个 agent，例如：
  - planner
  - retriever
  - executor

建议 commit 名称：
- `feat: add supervisor graph with specialized sub-agents`

测试要求：
- 多 agent 路径测试。
- 跑后端 `pytest` 全量回归。

建议手测：
- 复杂任务验证 delegation 是否合理。
- 检查状态汇总与 trace 是否仍然可读。

## 推荐执行顺序

1. Package 8
2. Package 8.5
3. Package 9
4. Package 9.5
5. Package 10
6. Package 11
7. Package 11.5
8. Package 12
9. Package 13
10. Package 14
11. Package 15
12. Package 16

## 每包固定交付格式

后续每推进一包，统一输出以下内容：

- 包名
- 目标
- 建议 commit 名称
- 改动文件
- 自动化测试结果
- 是否需要手测
- 手测步骤
- 风险与回退方案

## 当前建议

当前不要提前展开 MCP 或 multi-agent。优先打通这条核心链路：

`agent_v2 route -> retrieval/tool/clarify -> answer -> persistence/resume -> API -> frontend`

这条链路稳定后，再叠加 tracing、streaming、skill、MCP、multi-agent，成本最低，返工也最少。
