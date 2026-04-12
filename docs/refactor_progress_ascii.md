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

## Test Baseline

- Backend: `244 passed, 0 failed`
- Frontend: `16 passed, 0 failed`
