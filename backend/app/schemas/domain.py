from pydantic import BaseModel, Field


class ServiceRecord(BaseModel):
    service_id: str
    service_name: str
    owner_team: str = "platform-operations"
    tier: str = "tier-2"
    environments: list[str] = Field(default_factory=list)
    runbook_doc_ids: list[str] = Field(default_factory=list)


class StatusSnapshot(BaseModel):
    service: str
    environment: str
    health: str
    latency_p95_ms: int | None = None
    error_rate: float | None = None
    cpu_percent: float | None = None
    memory_percent: float | None = None
    active_alerts: list[str] = Field(default_factory=list)
    updated_at: str
    summary: str = ""


class IncidentTicket(BaseModel):
    ticket_id: str
    title: str
    service: str
    environment: str
    severity: str
    symptoms: list[str] = Field(default_factory=list)
    status: str
    assignee: str | None = None
    created_at: str
    updated_at: str
    source_run_id: str | None = None
    summary: str = ""


class KnowledgeAsset(BaseModel):
    doc_id: str
    service: str = ""
    doc_kind: str = "reference"
    section_path: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source_filename: str
    title: str = ""
    snippet: str = ""

