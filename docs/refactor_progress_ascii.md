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

## Test Baseline

- Backend: `233 passed, 0 failed`
- Frontend: `16 passed, 0 failed`
