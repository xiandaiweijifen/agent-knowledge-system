# Domain Model

This project is being narrowed toward an internal engineering support and
incident-assistance product. The core design rule is that tools, workflows,
frontend cards, and evaluation cases should all operate on the same business
objects instead of ad hoc text blobs.

## Core Objects

### Service

Represents a service or owned runtime surface.

Suggested fields:

- `service_id`
- `service_name`
- `owner_team`
- `tier`
- `environments`
- `runbook_doc_ids`

Usage:

- target for `system_status`
- target for `ticketing`
- filter anchor for `document_search`
- primary identifier in incident workflows

### IncidentTicket

Represents an operational issue record or work item.

Suggested fields:

- `ticket_id`
- `title`
- `service`
- `environment`
- `severity`
- `symptoms`
- `status`
- `assignee`
- `created_at`
- `updated_at`
- `source_run_id`
- `summary`

Usage:

- `ticketing:create|update|close|query|list`
- workflow checkpoint state
- approval and confirmation boundaries
- frontend ticket draft and incident cards

### StatusSnapshot

Represents a structured service health snapshot.

Suggested fields:

- `service`
- `environment`
- `health`
- `latency_p95_ms`
- `error_rate`
- `cpu_percent`
- `memory_percent`
- `active_alerts`
- `updated_at`
- `summary`

Usage:

- `system_status:query`
- status cards in the frontend
- threshold and escalation policy evaluation
- evidence aggregation for incident creation

### KnowledgeAsset

Represents a knowledge document or matched retrieval/search asset.

Suggested fields:

- `doc_id`
- `service`
- `doc_kind`
- `section_path`
- `tags`
- `source_filename`
- `title`
- `snippet`

Usage:

- `document_search:query`
- retrieval evidence cards
- runbook and FAQ filtering
- workflow evidence aggregation

## Tool Contract Shape

Each tool should expose a stable contract with:

- `tool_name`
- `action`
- `target`
- `arguments`
- `execution_status`
- `result_summary`
- `output`

The `output` payload should include both:

1. backwards-compatible flat fields already used by current flows
2. a structured domain object or collection for the primary business entity

Examples:

- `system_status` returns `service_record` and `status_snapshot`
- `ticketing` returns `ticket_record` or `ticket_records`
- `document_search` returns `knowledge_assets`

## Immediate Development Rule

New functionality should answer one question:

Does this make the incident-handling loop more complete?

If not, it should not be prioritized ahead of:

- stronger service modeling
- better status evidence
- safer incident ticket drafting
- more explicit SOP workflows
