# Demo Playbook

## Purpose

This playbook defines the strongest repeatable demo paths for the current system.

Use it when you need to:

- demonstrate the runtime end-to-end
- record a walkthrough
- rehearse project narration for interviews
- validate that the most important recovery and evaluation paths still work

## Recommended Demo Path

The strongest default path is:

1. Trigger a failed `agent_v2` tool run.
2. Observe retry exhaustion and structured recovery semantics.
3. Recover the workflow from the Query UI or recovery API.
4. Inspect lineage and recovery chain navigation.
5. Open the Evaluation workspace and show benchmark highlights, overview metrics, latest saved results, and report history.

This path demonstrates:

- `agent_v2` runtime behavior
- workflow persistence
- retry handling
- failed-step recovery
- recovery lineage
- evaluation dashboards

## Scenario A: Failed-Step Recovery

### Goal

Show that a failed `agent_v2` tool run can expose structured recovery actions and complete after recovery.

### API Setup

Request:

```json
{
  "question": "Create a high severity ticket for payment-service outage",
  "debug_fault_injection": {
    "tool_execution_failures": [
      {
        "tool_name": "ticketing",
        "action": "create",
        "fail_count": 1,
        "message": "demo injected persistent failure"
      }
    ]
  }
}
```

Expected source run shape:

- `workflow_status = failed`
- `retry_state = retry_exhausted`
- `recommended_recovery_action = resume_from_failed_step`
- `available_recovery_actions` includes:
  - `resume_from_failed_step`
  - `manual_retrigger`

### Recovery

Recover with:

```json
{
  "run_id": "<source_run_id>",
  "recovery_action": "resume_from_failed_step",
  "clarification_context": {}
}
```

Expected recovered run shape:

- `workflow_status = completed`
- `recovered_via_action = resume_from_failed_step`
- `resume_strategy = failed_step_resume`
- `source_run_id = <source_run_id>`
- `root_run_id = <source_run_id>`
- `recovery_depth = 1`
- `resumed_from_step_index = 1`
- `retried_step_indices = [1]`

### UI Checks

In `Query Lab`, verify:

- `Recovery Semantics` shows the failed-step action before recovery
- `Workflow Record` shows:
  - `Root Run`
  - `Source Run`
  - `Recovery Depth`
  - `Recovered Via`
- `Recovery Chain` shows both the failed source run and recovered run
- `Recent Workflow Runs` groups the chain correctly

## Scenario B: Clarification Recovery

### Goal

Show that a paused `agent_v2` run can collect missing fields and continue through the same recovery surface.

### API Setup

Request:

```json
{
  "question": "Fix it"
}
```

Expected source run shape:

- `workflow_status = clarification_required`
- `recommended_recovery_action = resume_with_clarification`
- `available_recovery_actions = ["resume_with_clarification"]`

### Recovery

Fill the clarification form in `Query Lab` or call recovery with:

```json
{
  "run_id": "<source_run_id>",
  "recovery_action": "resume_with_clarification",
  "clarification_context": {
    "environment": "production",
    "task_details": "check system status for payment-service"
  }
}
```

Expected recovered run shape:

- `workflow_status = completed`
- `recovered_via_action = resume_with_clarification`
- `question_rewritten = true`
- `applied_clarification_fields` contains the provided fields

## Scenario C: Evaluation Walkthrough

### Goal

Show that the project has repeatable benchmarks, persisted reports, and summary surfaces.

### Retrieval

Recommended dataset:

- `agent_workflow_retrieval_eval.json`

Suggested setting:

- `top_k = 3`

Show:

- `Evaluation Highlights`
- `Evaluation Overview`
- `Latest Saved Result`
- `Report Source`
- `Vs Previous`
- `Recent Evaluation History`

### Tool Execution

Recommended dataset:

- `agent_tool_execution_eval.json`

Show:

- `Tool Accuracy`
- case-level expected vs actual tool/action results
- saved report history

## Suggested Demo Order

Use this order in a live walkthrough:

1. `Query Lab`
2. Run failed-step recovery scenario
3. Show source run, recovered run, and recovery chain
4. Show grouped recent chains
5. Switch to `Evaluation`
6. Show highlights, overview, latest saved report, and history
7. Optionally run `Tool Execution` evaluation live

## Quick Checklist

- Backend and frontend are both running
- Retrieval artifacts exist for the demo documents
- At least one saved evaluation report exists
- `Evaluation Overview` cache is populated
- `Evaluation Highlights` is populated
- Query UI shows recent workflow runs
- Recovery actions are visible for the selected failed run

## Supporting Files

- `scripts/demo_recovery_flow.ps1`
- `data/tool_state/evaluation_reports/`
- `data/tool_state/evaluation_overview_cache.json`
- `data/tool_state/evaluation_metrics_summary.json`
