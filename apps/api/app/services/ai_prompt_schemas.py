"""Pydantic schemas for AI responses."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AISurrogateSummaryOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str
    recent_activity: str
    suggested_next_steps: list[str] = Field(default_factory=list)


class AIDraftEmailOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    subject: str
    body: str


class AIDashboardAnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    insights: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class AIImportMappingSuggestion(BaseModel):
    model_config = ConfigDict(extra="ignore")

    column: str
    suggested_field: str | None = None
    confidence: float = 0.0
    transformation: str | None = None
    invert: bool = False
    reasoning: str = ""
    action: str = "ignore"
    custom_field: dict[str, Any] | None = None


class AIChatActionProposal(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["send_email", "create_task", "add_note", "update_status"]
