"""Advanced analytics API router."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Any
from uuid import UUID

from core_app.api.dependencies import get_db, get_current_user
from core_app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/denial-patterns")
def analyze_denial_patterns(
    lookback_days: int = 30,
    min_occurrences: int = 3,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Analyze patterns in claim denials."""
    service = AnalyticsService(db)
    tenant_id = UUID(current_user["tenant_id"])

    result = service.analyze_denial_patterns(
        tenant_id=tenant_id,
        lookback_days=lookback_days,
        min_occurrences=min_occurrences,
    )

    return result


@router.get("/roi-metrics")
def calculate_roi_metrics(
    module: str | None = None,
    lookback_days: int = 30,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Calculate ROI metrics for AI usage."""
    service = AnalyticsService(db)
    tenant_id = UUID(current_user["tenant_id"])

    result = service.calculate_roi_metrics(
        tenant_id=tenant_id,
        module=module,
        lookback_days=lookback_days,
    )

    return result


@router.get("/prompt-performance")
def analyze_prompt_performance(
    module: str | None = None,
    task_type: str | None = None,
    lookback_days: int = 7,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Analyze prompt performance metrics."""
    service = AnalyticsService(db)
    tenant_id = UUID(current_user["tenant_id"])

    result = service.analyze_prompt_performance(
        tenant_id=tenant_id,
        module=module,
        task_type=task_type,
        lookback_days=lookback_days,
    )

    return result


@router.get("/model-effectiveness")
def compare_model_effectiveness(
    lookback_days: int = 7,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Compare effectiveness of different models."""
    service = AnalyticsService(db)
    tenant_id = UUID(current_user["tenant_id"])

    result = service.compare_model_effectiveness(
        tenant_id=tenant_id,
        lookback_days=lookback_days,
    )

    return result


@router.get("/cost-optimization")
def generate_cost_optimization_recommendations(
    lookback_days: int = 7,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Generate cost optimization recommendations."""
    service = AnalyticsService(db)
    tenant_id = UUID(current_user["tenant_id"])

    result = service.generate_cost_optimization_recommendations(
        tenant_id=tenant_id,
        lookback_days=lookback_days,
    )

    return result
