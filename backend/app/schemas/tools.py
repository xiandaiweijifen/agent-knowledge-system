from typing import Any

from pydantic import BaseModel, Field


class ToolExecutionRequest(BaseModel):
    tool_name: str
    action: str
    target: str
    arguments: dict[str, str] = Field(default_factory=dict)


class ToolExecutionResponse(BaseModel):
    tool_name: str
    action: str
    target: str
    execution_status: str
    execution_mode: str
    result_summary: str
    trace_id: str
    executed_at: str
    output: dict[str, Any] = Field(default_factory=dict)


class InferredToolRequest(BaseModel):
    tool_name: str
    action: str
    target: str


class ToolPlanRequest(BaseModel):
    question: str


class ToolPlanResponse(BaseModel):
    question: str
    planning_mode: str
    route_hint: str
    tool_name: str
    action: str
    target: str
    arguments: dict[str, str] = Field(default_factory=dict)
    plan_summary: str


class ToolCatalogEntry(BaseModel):
    tool_name: str
    supported_actions: list[str] = Field(default_factory=list)
    description: str
    execution_mode: str


class ToolCatalogResponse(BaseModel):
    count: int
    tools: list[ToolCatalogEntry] = Field(default_factory=list)
