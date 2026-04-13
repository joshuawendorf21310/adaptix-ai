"""Real AI governance endpoints (replaces shell implementation)."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from core_app.api.dependencies import CurrentUser, get_current_user
from core_app.database import get_db
from core_app.models.execution import ExecutionRequest, ExecutionResult
from core_app.services import PromptService, PolicyService, UsageService

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


@router.get('/prompts/audit')
async def prompt_audit(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get prompt governance audit summary.

    Returns truthful statistics from the database about prompts,
    active versions, guardrails, and usage.
    """
    prompt_service = PromptService(db)
    policy_service = PolicyService(db)
    usage_service = UsageService(db)

    # Get prompt statistics
    stats = prompt_service.get_prompt_statistics(current_user.tenant_id)

    # Get active policy
    active_policy = policy_service.get_active_policy(current_user.tenant_id)

    # Get today's usage
    usage_today = usage_service.get_daily_usage(current_user.tenant_id)

    # Get latency metrics
    latency = usage_service.get_latency_percentiles(current_user.tenant_id)

    # Build active prompts list
    active_versions = stats["active_versions"]
    prompts_list = [
        {
            "id": str(v.id),
            "name": f"v{v.version_number}",
            "version": v.version_number,
            "guardrails": v.guardrails_enabled,
            "pii_masking": v.pii_masking_enabled,
        }
        for v in active_versions
    ]

    return {
        "total_prompts": stats["total_prompts"],
        "active_prompts": stats["active_prompts"],
        "guardrails_enabled": stats["guardrails_enabled_count"] > 0,
        "pii_masking_enabled": stats["pii_masking_enabled_count"] > 0,
        "rate_limit_per_minute": active_policy.rate_limit_per_minute if active_policy else 0,
        "total_calls_today": usage_today["total_requests"],
        "avg_latency_ms": int(latency.get("p50", 0)),
        "prompts": prompts_list,
        "mode": "production",
        "as_of": datetime.now(UTC).isoformat(),
    }


@router.get('/prompt-log')
async def prompt_log(
    limit: int = 20,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """
    Get recent AI execution log.

    Returns actual execution history from the database.
    """
    # Query recent executions
    query = (
        select(ExecutionRequest, ExecutionResult)
        .join(ExecutionResult, ExecutionRequest.id == ExecutionResult.request_id, isouter=True)
        .where(ExecutionRequest.tenant_id == current_user.tenant_id)
        .order_by(ExecutionRequest.created_at.desc())
        .limit(limit)
    )

    results = db.execute(query).all()

    log_entries = []
    for req, res in results:
        entry = {
            "id": str(req.id),
            "correlation_id": req.correlation_id,
            "module": req.module,
            "task_type": req.task_type,
            "model_provider": req.model_provider,
            "model_id": req.model_id,
            "status": req.status,
            "created_at": req.created_at.isoformat(),
            "completed_at": req.completed_at.isoformat() if req.completed_at else None,
        }

        if res:
            entry.update({
                "success": res.success,
                "tokens": res.total_tokens,
                "latency_ms": res.latency_ms,
                "cost": res.estimated_cost,
                "error": res.error_message if not res.success else None,
            })

        log_entries.append(entry)

    return log_entries
