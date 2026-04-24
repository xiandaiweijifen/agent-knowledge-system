from pydantic import BaseModel, Field


class SkillDefinition(BaseModel):
    skill_id: str
    skill_label: str
    description: str
    owned_tools: list[str] = Field(default_factory=list)
    workflow_families: list[str] = Field(default_factory=list)


class SkillTraceRecord(BaseModel):
    skill_id: str
    skill_label: str
    status: str
    summary: str
    tool_names: list[str] = Field(default_factory=list)
