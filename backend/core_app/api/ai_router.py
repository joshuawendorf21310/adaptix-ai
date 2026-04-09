"""AI router — AWS Bedrock-powered narrative assist, ICD-10 suggestions, coding assist.

Requires:
  AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION, BEDROCK_MODEL_ID
All set in .env / environment. If unavailable, returns structured error — never silently fails.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core_app.ai.bedrock_service import (
    BedrockClient,
    BedrockClientError,
    BedrockRateLimitError,
    BedrockThrottlingError,
)
from core_app.ai.orchestrator import AiOrchestrator, AiTaskRequest
from core_app.ai.service import AiService
from core_app.api.dependencies import (
    db_session_dependency,
    get_ai_orchestrator,
    get_ai_service,
    get_current_user,
)
from core_app.core.config import get_settings
from core_app.schemas.ai import (
    AiHealthResponse,
    DeploymentRecommendationRequest,
    GenericAiTaskRequest,
    IncidentSummaryRequest,
    NarrativeGenerationRequest,
)
from core_app.schemas.auth import CurrentUser

from ..models import PromptCategory, PromptLog
from ..services.audit_service import AuditService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

# ---------------------------------------------------------------------------
# Prompt log (in-memory — replace with DB model in Phase 20 hardening)
# ---------------------------------------------------------------------------
_prompt_log: list[dict] = []
_ai_jobs: dict[str, dict[str, Any]] = {}


def _extract_bedrock_json(
    raw_text: str,
    *,
    expected: Literal["array", "object"],
    fallback: list[dict[str, Any]] | dict[str, Any],
) -> list[dict[str, Any]] | dict[str, Any]:
    """Extract structured JSON from Bedrock response with type-safe fallback.

    Ensures the returned type (parsed or fallback) matches expected type.
    Type guards prevent fallback type mismatch.

    Args:
        raw_text: Raw Bedrock response text
        expected: Expected JSON type ("array" or "object")
        fallback: Default value if parse fails; MUST match expected type

    Returns:
        Parsed JSON (list or dict) or fallback; type guaranteed to match expected
    """
    try:
        parsed = BedrockClient.parse_json_content(raw_text, expected=expected)
    except BedrockClientError as exc:
        logger.warning("Bedrock structured output parse failed: %s", exc)
        return fallback

    # Type guards: ensure parsed type matches expected, return fallback if not
    if expected == "array":
        if isinstance(parsed, list):
            return parsed
        # Parsed is wrong type; return fallback (which must be list)
        logger.warning(
            "Bedrock returned wrong type: expected array but got %s; using fallback",
            type(parsed).__name__,
        )
        return fallback

    # expected == "object"
    if isinstance(parsed, dict):
        return parsed
    # Parsed is wrong type; return fallback (which must be dict)
    logger.warning(
        "Bedrock returned wrong type: expected object but got %s; using fallback",
        type(parsed).__name__,
    )
    return fallback


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class NarrativeAssistRequest(BaseModel):
    dispatch_notes: str = Field(..., max_length=2000)
    chief_complaint: str | None = Field(None, max_length=500)
    assessment_notes: str | None = Field(None, max_length=2000)
    procedures: str | None = Field(None, max_length=1000)
    patient_age: int | None = None
    transport_mode: str | None = None


class NarrativeAssistResponse(BaseModel):
    narrative: str
    model_id: str
    prompt_log_id: str
    generated_at: datetime


class Icd10SuggestRequest(BaseModel):
    chief_complaint: str = Field(..., max_length=500)
    assessment_notes: str | None = Field(None, max_length=2000)
    top_n: int = Field(5, ge=1, le=10)


class Icd10SuggestResponse(BaseModel):
    suggestions: list[dict]
    model_id: str
    prompt_log_id: str
    generated_at: datetime


class CodingAssistRequest(BaseModel):
    procedures_narrative: str = Field(..., max_length=2000)
    medications_given: str | None = Field(None, max_length=1000)


class CodingAssistResponse(BaseModel):
    cpt_suggestions: list[dict]
    hcpcs_suggestions: list[dict]
    model_id: str
    prompt_log_id: str
    generated_at: datetime


# ---------------------------------------------------------------------------
# PHI-safe prompt builder helpers
# ---------------------------------------------------------------------------

def _build_narrative_prompt(req: NarrativeAssistRequest) -> str:
    parts = [
        "You are an expert EMS documentation assistant. Generate a professional, factual EMS PCR narrative.",
        "Use only the information provided. Do not invent details. Use past tense. Be concise and clinically accurate.",
        "",
        f"Dispatch notes: {req.dispatch_notes}",
    ]
    if req.chief_complaint:
        parts.append(f"Chief complaint: {req.chief_complaint}")
    if req.patient_age:
        parts.append(f"Patient age: {req.patient_age}")
    if req.assessment_notes:
        parts.append(f"Assessment: {req.assessment_notes}")
    if req.procedures:
        parts.append(f"Procedures performed: {req.procedures}")
    if req.transport_mode:
        parts.append(f"Transport mode: {req.transport_mode}")
    parts += [
        "",
        "Write a structured narrative (subjective, objective, assessment, plan format preferred).",
        "Narrative:",
    ]
    return "\n".join(parts)


def _build_icd10_prompt(req: Icd10SuggestRequest) -> str:
    parts = [
        f"You are a clinical coding specialist. Suggest the top {req.top_n} ICD-10-CM codes most relevant to the following EMS encounter.",
        "Return ONLY valid JSON array of objects with keys: code, description, confidence (high/medium/low).",
        f"Chief complaint: {req.chief_complaint}",
    ]
    if req.assessment_notes:
        parts.append(f"Assessment: {req.assessment_notes}")
    parts.append("JSON:")
    return "\n".join(parts)


def _build_coding_prompt(req: CodingAssistRequest) -> str:
    return (
        "You are a medical billing coding specialist. Suggest CPT and HCPCS codes for EMS procedures.\n"
        "Return ONLY valid JSON with keys: cpt_suggestions (array of {code, description, confidence}), "
        "hcpcs_suggestions (array of {code, description, confidence}).\n"
        f"Procedures narrative: {req.procedures_narrative}\n"
        + (f"Medications given: {req.medications_given}\n" if req.medications_given else "")
        + "JSON:"
    )


def _log_prompt(tenant_id: str, user_id: str, prompt_type: str, model_id: str) -> str:
    log_id = str(uuid4())
    _prompt_log.append({
        "id": log_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "prompt_type": prompt_type,
        "model_id": model_id,
        "logged_at": datetime.now(UTC).isoformat(),
    })
    logger.info("AI prompt logged: %s type=%s user=%s", log_id, prompt_type, user_id)
    return log_id


def _actor_role(current_user: CurrentUser) -> str:
    return str(getattr(current_user, "resolved_primary_role", None) or current_user.role)


async def _run_orchestrated_task(
    *,
    current_user: CurrentUser,
    orchestrator: AiOrchestrator,
    module: str,
    task_type: str,
    correlation_id: str,
    context: dict[str, Any],
    priority: str = "interactive",
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> dict[str, Any]:
    result = await orchestrator.run(
        AiTaskRequest(
            tenant_id=str(current_user.tenant_id),
            actor_id=str(current_user.user_id),
            actor_role=_actor_role(current_user),
            module=module,
            task_type=task_type,
            priority=priority,
            correlation_id=correlation_id,
            context=context,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    )
    return result.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/narrative-assist", response_model=NarrativeAssistResponse)
async def narrative_assist(
    body: NarrativeAssistRequest,
    db: Session = Depends(db_session_dependency),
    current_user: CurrentUser = Depends(get_current_user),
    ai_service: AiService = Depends(get_ai_service),
) -> NarrativeAssistResponse:
    """Generate an ePCR narrative using AWS Bedrock Claude."""
    prompt = _build_narrative_prompt(body)
    try:
        result = await ai_service.generate_text(prompt=prompt, max_tokens=800, temperature=0.2)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="AI features are currently unavailable") from exc
    except BedrockRateLimitError as exc:
        logger.warning("bedrock_rate_limited narrative_assist error=%s", exc)
        raise HTTPException(status_code=429, detail="AI service rate limited", headers={"Retry-After": "60"}) from exc
    except BedrockThrottlingError as exc:
        logger.warning("bedrock_throttled narrative_assist error=%s", exc)
        raise HTTPException(status_code=503, detail="AI service temporarily throttled", headers={"Retry-After": "30"}) from exc
    except BedrockClientError as exc:
        logger.error("Bedrock narrative generation failed: %s", exc)
        raise HTTPException(status_code=502, detail="AI narrative generation failed") from exc

    narrative = str(result.get("text") or "")
    model_name = str(result.get("model") or ai_service.model_name)
    log_id = _log_prompt(str(current_user.tenant_id), str(current_user.user_id), "narrative_assist", model_name)
    return NarrativeAssistResponse(
        narrative=narrative.strip(),
        model_id=model_name,
        prompt_log_id=log_id,
        generated_at=datetime.now(UTC),
    )


@router.post("/icd10-suggest", response_model=Icd10SuggestResponse)
async def icd10_suggest(
    body: Icd10SuggestRequest,
    db: Session = Depends(db_session_dependency),
    current_user: CurrentUser = Depends(get_current_user),
    ai_service: AiService = Depends(get_ai_service),
) -> Icd10SuggestResponse:
    """Suggest ICD-10-CM codes using AWS Bedrock."""
    prompt = _build_icd10_prompt(body)
    try:
        result = await ai_service.generate_text(prompt=prompt, max_tokens=512, temperature=0)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="AI features are currently unavailable") from exc
    except BedrockRateLimitError as exc:
        logger.warning("bedrock_rate_limited icd10_suggest error=%s", exc)
        raise HTTPException(status_code=429, detail="AI service rate limited", headers={"Retry-After": "60"}) from exc
    except BedrockThrottlingError as exc:
        logger.warning("bedrock_throttled icd10_suggest error=%s", exc)
        raise HTTPException(status_code=503, detail="AI service temporarily throttled", headers={"Retry-After": "30"}) from exc
    except BedrockClientError as exc:
        logger.error("Bedrock ICD-10 suggestion failed: %s", exc)
        raise HTTPException(status_code=502, detail="ICD-10 suggestion failed") from exc

    raw = str(result.get("text") or "")
    suggestions_raw = _extract_bedrock_json(
        raw,
        expected=cast(Literal["array", "object"], "array"),
        fallback=[{"code": "PARSE_ERROR", "description": "AI response could not be parsed", "confidence": "low"}],
    )
    suggestions = suggestions_raw if isinstance(suggestions_raw, list) else []

    model_name = str(result.get("model") or ai_service.model_name)
    log_id = _log_prompt(str(current_user.tenant_id), str(current_user.user_id), "icd10_suggest", model_name)
    return Icd10SuggestResponse(
        suggestions=suggestions,
        model_id=model_name,
        prompt_log_id=log_id,
        generated_at=datetime.now(UTC),
    )


@router.post("/coding-assist", response_model=CodingAssistResponse)
async def coding_assist(
    body: CodingAssistRequest,
    db: Session = Depends(db_session_dependency),
    current_user: CurrentUser = Depends(get_current_user),
    ai_service: AiService = Depends(get_ai_service),
) -> CodingAssistResponse:
    """Suggest CPT/HCPCS procedure codes using AWS Bedrock."""
    prompt = _build_coding_prompt(body)
    try:
        result = await ai_service.generate_text(prompt=prompt, max_tokens=512, temperature=0)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="AI features are currently unavailable") from exc
    except BedrockRateLimitError as exc:
        logger.warning("bedrock_rate_limited coding_assist error=%s", exc)
        raise HTTPException(status_code=429, detail="AI service rate limited", headers={"Retry-After": "60"}) from exc
    except BedrockThrottlingError as exc:
        logger.warning("bedrock_throttled coding_assist error=%s", exc)
        raise HTTPException(status_code=503, detail="AI service temporarily throttled", headers={"Retry-After": "30"}) from exc
    except BedrockClientError as exc:
        logger.error("Bedrock coding assist failed: %s", exc)
        raise HTTPException(status_code=502, detail="Coding assist failed") from exc

    raw = str(result.get("text") or "")
    parsed_raw = _extract_bedrock_json(
        raw,
        expected=cast(Literal["array", "object"], "object"),
        fallback={"cpt_suggestions": [], "hcpcs_suggestions": []},
    )
    parsed = parsed_raw if isinstance(parsed_raw, dict) else {}
    cpt = parsed.get("cpt_suggestions", [])
    hcpcs = parsed.get("hcpcs_suggestions", [])

    model_name = str(result.get("model") or ai_service.model_name)
    log_id = _log_prompt(str(current_user.tenant_id), str(current_user.user_id), "coding_assist", model_name)
    return CodingAssistResponse(
        cpt_suggestions=cpt,
        hcpcs_suggestions=hcpcs,
        model_id=model_name,
        prompt_log_id=log_id,
        generated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Adaptix module AI routes (centralized orchestration)
# ---------------------------------------------------------------------------


@router.post("/command/incident-summary")
async def command_incident_summary(
    body: IncidentSummaryRequest,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: AiOrchestrator = Depends(get_ai_orchestrator),
):
    return await _run_orchestrated_task(
        current_user=current_user,
        orchestrator=orchestrator,
        module="command",
        task_type="incident_summary",
        correlation_id=body.correlation_id,
        context=body.model_dump(),
    )


@router.post("/command/operating-picture")
async def command_operating_picture(
    body: IncidentSummaryRequest,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: AiOrchestrator = Depends(get_ai_orchestrator),
):
    return await _run_orchestrated_task(
        current_user=current_user,
        orchestrator=orchestrator,
        module="command",
        task_type="operating_picture",
        correlation_id=body.correlation_id,
        context=body.model_dump(),
    )


@router.post("/command/deployment-recommendation")
async def command_deployment_recommendation(
    body: DeploymentRecommendationRequest,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: AiOrchestrator = Depends(get_ai_orchestrator),
):
    return await _run_orchestrated_task(
        current_user=current_user,
        orchestrator=orchestrator,
        module="command",
        task_type="deployment_recommendation",
        correlation_id=body.correlation_id,
        context=body.model_dump(),
    )


@router.post("/field/narrative-generation")
async def field_narrative_generation(
    body: NarrativeGenerationRequest,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: AiOrchestrator = Depends(get_ai_orchestrator),
):
    return await _run_orchestrated_task(
        current_user=current_user,
        orchestrator=orchestrator,
        module="field",
        task_type="narrative_generation",
        correlation_id=body.correlation_id,
        context=body.model_dump(),
    )


@router.post("/field/scene-summary")
async def field_scene_summary(
    body: NarrativeGenerationRequest,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: AiOrchestrator = Depends(get_ai_orchestrator),
):
    return await _run_orchestrated_task(
        current_user=current_user,
        orchestrator=orchestrator,
        module="field",
        task_type="scene_summary",
        correlation_id=body.correlation_id,
        context=body.model_dump(),
    )


@router.post("/field/handoff-summary")
async def field_handoff_summary(
    body: NarrativeGenerationRequest,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: AiOrchestrator = Depends(get_ai_orchestrator),
):
    return await _run_orchestrated_task(
        current_user=current_user,
        orchestrator=orchestrator,
        module="field",
        task_type="handoff_summary",
        correlation_id=body.correlation_id,
        context=body.model_dump(),
    )


@router.post("/flow/coverage-analysis")
async def flow_coverage_analysis(
    body: DeploymentRecommendationRequest,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: AiOrchestrator = Depends(get_ai_orchestrator),
):
    return await _run_orchestrated_task(
        current_user=current_user,
        orchestrator=orchestrator,
        module="flow",
        task_type="coverage_analysis",
        correlation_id=body.correlation_id,
        context=body.model_dump(),
    )


@router.post("/flow/redeployment-recommendation")
async def flow_redeployment_recommendation(
    body: DeploymentRecommendationRequest,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: AiOrchestrator = Depends(get_ai_orchestrator),
):
    return await _run_orchestrated_task(
        current_user=current_user,
        orchestrator=orchestrator,
        module="flow",
        task_type="redeployment_recommendation",
        correlation_id=body.correlation_id,
        context=body.model_dump(),
    )


@router.post("/flow/transport-bottleneck-analysis")
async def flow_transport_bottleneck_analysis(
    body: DeploymentRecommendationRequest,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: AiOrchestrator = Depends(get_ai_orchestrator),
):
    return await _run_orchestrated_task(
        current_user=current_user,
        orchestrator=orchestrator,
        module="flow",
        task_type="transport_bottleneck_analysis",
        correlation_id=body.correlation_id,
        context=body.model_dump(),
    )


@router.post("/pulse/fatigue-analysis")
async def pulse_fatigue_analysis(
    body: GenericAiTaskRequest,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: AiOrchestrator = Depends(get_ai_orchestrator),
):
    return await _run_orchestrated_task(
        current_user=current_user,
        orchestrator=orchestrator,
        module="pulse",
        task_type="fatigue_analysis",
        correlation_id=body.correlation_id,
        context=body.context,
    )


@router.post("/pulse/readiness-summary")
async def pulse_readiness_summary(
    body: GenericAiTaskRequest,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: AiOrchestrator = Depends(get_ai_orchestrator),
):
    return await _run_orchestrated_task(
        current_user=current_user,
        orchestrator=orchestrator,
        module="pulse",
        task_type="readiness_summary",
        correlation_id=body.correlation_id,
        context=body.context,
    )


@router.post("/air/mission-brief")
async def air_mission_brief(
    body: GenericAiTaskRequest,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: AiOrchestrator = Depends(get_ai_orchestrator),
):
    return await _run_orchestrated_task(
        current_user=current_user,
        orchestrator=orchestrator,
        module="air",
        task_type="mission_brief",
        correlation_id=body.correlation_id,
        context=body.context,
    )


@router.post("/air/launch-context")
async def air_launch_context(
    body: GenericAiTaskRequest,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: AiOrchestrator = Depends(get_ai_orchestrator),
):
    return await _run_orchestrated_task(
        current_user=current_user,
        orchestrator=orchestrator,
        module="air",
        task_type="launch_context",
        correlation_id=body.correlation_id,
        context=body.context,
    )


@router.post("/interop/cross-system-interpretation")
async def interop_cross_system_interpretation(
    body: GenericAiTaskRequest,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: AiOrchestrator = Depends(get_ai_orchestrator),
):
    return await _run_orchestrated_task(
        current_user=current_user,
        orchestrator=orchestrator,
        module="interop",
        task_type="cross_system_interpretation",
        correlation_id=body.correlation_id,
        context=body.context,
    )


@router.post("/interop/source-reconciliation")
async def interop_source_reconciliation(
    body: GenericAiTaskRequest,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: AiOrchestrator = Depends(get_ai_orchestrator),
):
    return await _run_orchestrated_task(
        current_user=current_user,
        orchestrator=orchestrator,
        module="interop",
        task_type="source_reconciliation",
        correlation_id=body.correlation_id,
        context=body.context,
    )


@router.post("/insight/executive-summary")
async def insight_executive_summary(
    body: GenericAiTaskRequest,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: AiOrchestrator = Depends(get_ai_orchestrator),
):
    return await _run_orchestrated_task(
        current_user=current_user,
        orchestrator=orchestrator,
        module="insight",
        task_type="executive_summary",
        correlation_id=body.correlation_id,
        context=body.context,
    )


@router.post("/insight/performance-trend-summary")
async def insight_performance_trend_summary(
    body: GenericAiTaskRequest,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: AiOrchestrator = Depends(get_ai_orchestrator),
):
    return await _run_orchestrated_task(
        current_user=current_user,
        orchestrator=orchestrator,
        module="insight",
        task_type="performance_trend_summary",
        correlation_id=body.correlation_id,
        context=body.context,
    )


@router.post("/jobs")
async def submit_ai_job(
    body: GenericAiTaskRequest,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: AiOrchestrator = Depends(get_ai_orchestrator),
):
    job_id = str(uuid4())
    _ai_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "submitted_at": datetime.now(UTC).isoformat(),
        "correlation_id": body.correlation_id,
        "module": body.module,
        "task_type": body.task_type,
    }

    result = await _run_orchestrated_task(
        current_user=current_user,
        orchestrator=orchestrator,
        module=body.module,
        task_type=body.task_type,
        correlation_id=body.correlation_id,
        context=body.context,
        priority=body.priority,
        max_tokens=body.max_tokens,
        temperature=body.temperature,
    )

    _ai_jobs[job_id]["status"] = "completed"
    _ai_jobs[job_id]["completed_at"] = datetime.now(UTC).isoformat()
    _ai_jobs[job_id]["result"] = result
    return _ai_jobs[job_id]


@router.get("/jobs/{job_id}")
async def get_ai_job(job_id: str, current_user: CurrentUser = Depends(get_current_user)):
    job = _ai_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="AI job not found")
    return job


@router.get("/health", response_model=AiHealthResponse)
async def ai_health() -> AiHealthResponse:
    settings = get_settings()
    return AiHealthResponse(
        status="ok",
        ai_enabled=settings.enable_ai_features,
        provider=settings.ai_provider,
        bedrock_region=settings.bedrock_region or settings.aws_region or "",
    )


@router.get("/prompt-log")
async def get_prompt_log(
    limit: int = 50,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return AI prompt audit log for the current tenant."""
    if current_user.resolved_primary_role not in ("founder", "agency_admin"):
        raise HTTPException(status_code=403, detail="Founder or admin role required")
    tenant_logs = [
        log for log in _prompt_log
        if log["tenant_id"] == str(current_user.tenant_id)
    ]
    return {"logs": tenant_logs[-limit:], "total": len(tenant_logs)}


# ============================================================================
# Phase 20: Database Persistence for Prompts
# ============================================================================

def _log_prompt_to_db(
    db: Session,
    tenant_id: str,
    user_id: str,
    category: PromptCategory,
    prompt_text: str,
    response_text: str | None,
    model_used: str,
    request_id: str | None = None,
    latency_ms: int | None = None,
) -> str:
    """Persist prompt to database for audit trail (Phase 20 hardening)."""
    log_entry = PromptLog(
        tenant_id=UUID(tenant_id),
        user_id=UUID(user_id),
        category=category,
        prompt_text=prompt_text,
        response_text=response_text,
        model_used=model_used,
        request_id=request_id,
        latency_ms=latency_ms,
        flags=["logged"],
    )
    db.add(log_entry)
    db.flush()

    # Audit via AuditService
    audit = AuditService(db)
    audit.write(
        tenant_id=UUID(tenant_id),
        user_id=UUID(user_id),
        request_id=request_id,
        action="ai_prompt_logged",
        resource="PromptLog",
        resource_id=str(log_entry.id),
        before_state={},
        after_state={
            "category": category.value,
            "model_used": model_used,
        },
    )

    db.commit()
    return str(log_entry.id)


@router.get("/prompts/audit", response_model=dict)
async def get_prompt_audit_trail(
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(db_session_dependency),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get persistent AI prompt audit trail (Phase 20)."""
    if current_user.resolved_primary_role not in ("founder", "agency_admin"):
        raise HTTPException(status_code=403, detail="Founder or admin role required")

    tenant_id = current_user.tenant_id
    query = db.query(PromptLog).filter(PromptLog.tenant_id == tenant_id)

    if category:
        query = query.filter(PromptLog.category == category)

    total = query.count()
    logs = query.order_by(PromptLog.api_call_timestamp.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "logs": [{
            "id": str(log.id),
            "category": cast(Any, log.category).value if cast(Any, log.category) is not None else None,
            "model_used": log.model_used,
            "request_id": log.request_id,
            "was_accepted": log.was_accepted,
            "api_call_timestamp": log.api_call_timestamp.isoformat(),
            "latency_ms": log.latency_ms,
        } for log in logs],
    }


@router.get("/prompts/{prompt_id}")
async def get_prompt_log_detail(
    prompt_id: str,
    db: Session = Depends(db_session_dependency),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get detailed prompt log entry (Phase 20)."""
    tenant_id = current_user.tenant_id
    log_uuid = UUID(prompt_id)

    log_entry = db.query(PromptLog).filter(
        PromptLog.id == log_uuid,
        PromptLog.tenant_id == tenant_id,
    ).first()

    if not log_entry:
        raise HTTPException(status_code=404, detail="Prompt log not found")

    return {
        "id": str(log_entry.id),
        "category": cast(Any, log_entry.category).value if cast(Any, log_entry.category) is not None else None,
        "module": log_entry.module,
        "prompt_text": log_entry.prompt_text,
        "response_text": log_entry.response_text,
        "model_used": log_entry.model_used,
        "tokens_input": log_entry.tokens_input,
        "tokens_output": log_entry.tokens_output,
        "was_accepted": log_entry.was_accepted,
        "user_feedback": log_entry.user_feedback,
        "api_call_timestamp": log_entry.api_call_timestamp.isoformat(),
        "flags": log_entry.flags,
    }


@router.get("/audit/{prompt_log_id}")
async def get_ai_audit_detail(
    prompt_log_id: str,
    db: Session = Depends(db_session_dependency),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Compatibility alias for canonical AI audit detail lookup."""
    return await get_prompt_log_detail(
        prompt_id=prompt_log_id,
        db=db,
        current_user=current_user,
    )


@router.patch("/prompts/{prompt_id}/feedback")
async def record_prompt_feedback(
    prompt_id: str,
    was_accepted: bool,
    request: Request,
    db: Session = Depends(db_session_dependency),
    current_user: CurrentUser = Depends(get_current_user),
    feedback: str | None = None,
):
    """Record user feedback on AI response (Phase 20)."""
    tenant_id = current_user.tenant_id
    user_id = current_user.user_id
    log_uuid = UUID(prompt_id)
    request_id = getattr(request.state, "request_id", None) if request else None

    log_entry = db.query(PromptLog).filter(
        PromptLog.id == log_uuid,
        PromptLog.tenant_id == tenant_id,
    ).first()

    if not log_entry:
        raise HTTPException(status_code=404, detail="Prompt log not found")

    log_record = cast(Any, log_entry)
    log_record.was_accepted = was_accepted
    log_record.user_feedback = feedback
    existing_flags = cast(list[str], log_record.flags or [])
    log_record.flags = list(set(existing_flags + ["reviewed"]))

    db.flush()

    # Audit
    audit = AuditService(db)
    audit.write(
        tenant_id=tenant_id,
        user_id=user_id,
        request_id=request_id,
        action="prompt_feedback_recorded",
        resource="PromptLog",
        resource_id=str(log_entry.id),
        before_state={},
        after_state={
            "was_accepted": was_accepted,
            "feedback": feedback[:100] if feedback else None,
        },
    )

    db.commit()
    logger.info("Recorded feedback on prompt %s", prompt_id)

    return {"status": "recorded"}


# ---------------------------------------------------------------------------
# Setup Config — public endpoint (no auth required)
# ---------------------------------------------------------------------------


class SetupConfigRequest(BaseModel):
    service_type: str = Field(..., min_length=2, max_length=400)


class SetupConfigResponse(BaseModel):
    agencyType: str
    recommendedPlan: str
    modules: list[str]
    estimatedROI: int
    config: dict


_AGENCY_PROFILES: dict[str, dict] = {
    "911": {
        "agencyType": "911 EMS Agency",
        "recommendedPlan": "Enterprise",
        "modules": ["Dispatch", "ePCR", "CAD", "Billing", "CrewLink", "MDT"],
        "estimatedROI": 185000,
        "config": {"staffSize": 45, "vehicles": 14, "callVolume": 4200},
    },
    "private": {
        "agencyType": "Private EMS / Transport",
        "recommendedPlan": "Pro",
        "modules": ["Dispatch", "ePCR", "Billing", "TransportLink"],
        "estimatedROI": 127000,
        "config": {"staffSize": 25, "vehicles": 8, "callVolume": 1200},
    },
    "hospital": {
        "agencyType": "Hospital-Based EMS",
        "recommendedPlan": "Pro",
        "modules": ["ePCR", "Billing", "Compliance", "NEMSIS", "Scheduling"],
        "estimatedROI": 142000,
        "config": {"staffSize": 30, "vehicles": 10, "callVolume": 2800},
    },
    "fire": {
        "agencyType": "Fire Department EMS",
        "recommendedPlan": "Enterprise",
        "modules": ["CAD", "ePCR", "Dispatch", "CrewLink", "Compliance", "MDT"],
        "estimatedROI": 163000,
        "config": {"staffSize": 38, "vehicles": 12, "callVolume": 3100},
    },
    "interfacility": {
        "agencyType": "Interfacility Transport",
        "recommendedPlan": "Pro",
        "modules": ["TransportLink", "ePCR", "Billing", "Scheduling"],
        "estimatedROI": 98000,
        "config": {"staffSize": 18, "vehicles": 6, "callVolume": 900},
    },
}


def _classify_service_type(service_type: str) -> str:
    """Map free-text service description to a profile key."""
    text = service_type.lower()
    if any(k in text for k in ("911", "emergency", "municipal", "county", "city")):
        return "911"
    if any(k in text for k in ("fire", "fd ", "fire dept")):
        return "fire"
    if any(k in text for k in ("hospital", "health system", "medical center")):
        return "hospital"
    if any(k in text for k in ("interfacility", "inter-facility", "transfer", "critical care transport")):
        return "interfacility"
    return "private"


def _build_setup_config_prompt(service_type: str) -> str:
    return (
        f"You are an EMS operations specialist. A new agency has described their service as: '{service_type}'. "
        "Based on this description, return a JSON object (no markdown, no explanation, only raw JSON) with these fields: "
        "agencyType (string), recommendedPlan ('Starter'|'Pro'|'Enterprise'), modules (array of strings from: "
        "Dispatch, ePCR, CAD, Billing, TransportLink, CrewLink, MDT, Scheduling, Compliance, NEMSIS), "
        "estimatedROI (integer, annual USD improvement), config (object with staffSize, vehicles, callVolume integers). "
        "Return only valid JSON."
    )


@router.post("/setup-config", response_model=SetupConfigResponse)
async def setup_config(
    req: SetupConfigRequest,
    ai_service: AiService = Depends(get_ai_service),
) -> SetupConfigResponse:
    """
    Public endpoint — generates AI-recommended platform configuration for a given
    service type description.  Falls back to rule-based profiles if Bedrock unavailable.
    No authentication required (pre-signup context).
    """
    # Attempt Bedrock call first
    try:
        prompt = _build_setup_config_prompt(req.service_type)
        result = await ai_service.generate_text(prompt=prompt, max_tokens=512, temperature=0)
        parsed = _extract_bedrock_json(
            str(result.get("text") or ""),
            expected=cast(Literal["array", "object"], "object"),
            fallback={},
        )
        data = parsed if isinstance(parsed, dict) else {}
        modules_raw = data.get("modules", ["Dispatch", "ePCR", "Billing"])
        modules = [str(m) for m in modules_raw] if isinstance(modules_raw, list) else ["Dispatch", "ePCR", "Billing"]
        config_raw = data.get("config", {}) if isinstance(data.get("config", {}), dict) else {}
        return SetupConfigResponse(
            agencyType=str(data.get("agencyType", req.service_type)),
            recommendedPlan=str(data.get("recommendedPlan", "Pro")),
            modules=modules,
            estimatedROI=int(data.get("estimatedROI", 110000) if not isinstance(data.get("estimatedROI", 110000), list) else 110000),
            config={
                "staffSize": int(config_raw.get("staffSize", 20)),
                "vehicles": int(config_raw.get("vehicles", 6)),
                "callVolume": int(config_raw.get("callVolume", 1000)),
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("Bedrock unavailable for setup-config, using rule-based fallback: %s", exc)

    # Rule-based fallback
    key = _classify_service_type(req.service_type)
    profile = dict(_AGENCY_PROFILES[key])
    profile["agencyType"] = profile["agencyType"] if key != "private" else req.service_type.strip().title()
    return SetupConfigResponse(**profile)


