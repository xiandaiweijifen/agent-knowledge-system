from pydantic import BaseModel, Field


class ClarificationPlanResponse(BaseModel):
    question: str
    planning_mode: str
    missing_fields: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    clarification_summary: str
