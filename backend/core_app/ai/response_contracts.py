from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class RankedOption(BaseModel):
    option: str
    reason: str
    expected_effect: str


class IncidentSummaryOutput(BaseModel):
    headline: str = ""
    summary: str = ""
    priority_risks: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class NarrativeGenerationOutput(BaseModel):
    narrative: str = ""
    missing_elements: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)


class DeploymentRecommendationOutput(BaseModel):
    current_state: str = ""
    coverage_risk: str = ""
    ranked_options: list[RankedOption] = Field(default_factory=list)
    watch_items: list[str] = Field(default_factory=list)


class FatigueAnalysisOutput(BaseModel):
    readiness_level: str = ""
    risk_factors: list[str] = Field(default_factory=list)
    recommended_interventions: list[str] = Field(default_factory=list)
    confidence: str = "medium"


class CrossSystemInterpretationOutput(BaseModel):
    source_summary: str = ""
    normalized_interpretation: str = ""
    conflicts_detected: list[str] = Field(default_factory=list)
    probable_explanation: str = ""
    action_path: list[str] = Field(default_factory=list)


class ExecutiveSummaryOutput(BaseModel):
    executive_summary: str = ""
    major_findings: list[str] = Field(default_factory=list)
    operational_implications: list[str] = Field(default_factory=list)
    recommended_follow_up: list[str] = Field(default_factory=list)


class AiTaskResponse(BaseModel):
    ok: bool = True
    module: str
    task_type: str
    correlation_id: str
    model_provider: str = "aws-bedrock"
    model_id: str
    prompt_version: str
    usage: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime
    latency_ms: int
    errors: list[str] = Field(default_factory=list)


def normalize_result(
    *,
    module: str,
    task_type: str,
    correlation_id: str,
    model_id: str,
    parsed_output: dict[str, Any],
    usage: dict[str, Any] | None,
    prompt_version: str,
    started_at: datetime,
    completed_at: datetime,
) -> AiTaskResponse:
    latency_ms = max(int((completed_at - started_at).total_seconds() * 1000), 0)
    return AiTaskResponse(
        ok=True,
        module=module,
        task_type=task_type,
        correlation_id=correlation_id,
        model_id=model_id,
        prompt_version=prompt_version,
        usage=usage or {},
        result=parsed_output,
        started_at=started_at.astimezone(UTC),
        completed_at=completed_at.astimezone(UTC),
        latency_ms=latency_ms,
    )
