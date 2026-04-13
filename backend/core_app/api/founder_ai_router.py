"""Real founder AI system metrics (replaces shell implementation)."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core_app.api.dependencies import CurrentUser, get_current_user
from core_app.config import settings
from core_app.database import get_db
from core_app.services import PolicyService, SystemHealthService, UsageService

router = APIRouter(tags=['founder-ai'])


@router.get('/api/founder/system')
async def founder_system(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get founder AI system overview with truthful metrics.

    Returns real data from database about AI health, usage, budget, and performance.
    """
    usage_service = UsageService(db)
    health_service = SystemHealthService(db)
    policy_service = PolicyService(db)

    # Get today's usage
    usage_today = usage_service.get_daily_usage(current_user.tenant_id)

    # Get latency percentiles
    latency = usage_service.get_latency_percentiles(current_user.tenant_id)

    # Get active policy for budget
    active_policy = policy_service.get_active_policy(current_user.tenant_id)
    daily_budget = active_policy.daily_token_budget if active_policy else settings.daily_token_budget

    # Get provider health
    bedrock_health = health_service.get_latest_provider_health("aws-bedrock")

    # Calculate AI health status
    ai_healthy = bedrock_health.is_healthy if bedrock_health else False

    # Calculate error rate
    total_requests = usage_today["total_requests"]
    failed_requests = usage_today["failed_requests"]
    error_rate = (failed_requests / total_requests) if total_requests > 0 else 0.0

    return {
        'ai_healthy': ai_healthy,
        'bedrock_latency_p95': int(latency.get('p95', 0)),
        'daily_token_budget': daily_budget,
        'tokens_used_today': usage_today["total_tokens"],
        'error_rate': round(error_rate, 4),
        'as_of': datetime.now(UTC).isoformat(),
        'mode': 'production',
    }
