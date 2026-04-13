"""Budget management API router."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Any
from uuid import UUID

from core_app.api.dependencies import get_db, get_current_user
from core_app.services.budget_service import BudgetService
from core_app.models.budget import BudgetPeriod

router = APIRouter(prefix="/api/v1/budget", tags=["budget"])


class CreateBudgetRequest(BaseModel):
    """Request to create a budget."""
    scope_type: str = Field(..., description="Budget scope: tenant, module, task_type, user")
    scope_value: str | None = Field(None, description="Scope value (e.g., module name)")
    period: str = Field(..., description="Budget period: daily, weekly, monthly, quarterly, annual")
    limit_usd: float = Field(..., gt=0, description="Budget limit in USD")
    soft_cap_threshold: float = Field(0.9, ge=0, le=1, description="Soft cap threshold (0-1)")
    hard_cap_enabled: bool = Field(False, description="Enable hard cap enforcement")
    alert_enabled: bool = Field(True, description="Enable budget alerts")


class BudgetStatusResponse(BaseModel):
    """Budget status response."""
    exists: bool
    limit_usd: float | None = None
    consumed_usd: float | None = None
    remaining_usd: float | None = None
    utilization_pct: float | None = None
    request_count: int | None = None
    period_start: str | None = None
    period_end: str | None = None
    status: str | None = None
    is_soft_cap_exceeded: bool | None = None
    is_hard_cap_exceeded: bool | None = None


@router.post("/create", status_code=201)
def create_budget(
    request: CreateBudgetRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a new budget."""
    service = BudgetService(db)

    tenant_id = UUID(current_user["tenant_id"])
    user_id = UUID(current_user["user_id"])

    budget = service.create_budget(
        tenant_id=tenant_id,
        scope_type=request.scope_type,
        scope_value=request.scope_value,
        period=request.period,
        limit_usd=request.limit_usd,
        soft_cap_threshold=request.soft_cap_threshold,
        hard_cap_enabled=request.hard_cap_enabled,
        alert_enabled=request.alert_enabled,
        created_by=user_id,
    )

    return {
        "budget_id": str(budget.id),
        "status": "created",
        "message": f"Budget created for {request.scope_type}",
    }


@router.get("/status", response_model=BudgetStatusResponse)
def get_budget_status(
    scope_type: str,
    scope_value: str | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> BudgetStatusResponse:
    """Get current budget status."""
    service = BudgetService(db)
    tenant_id = UUID(current_user["tenant_id"])

    status = service.get_budget_status(
        tenant_id=tenant_id,
        scope_type=scope_type,
        scope_value=scope_value,
    )

    return BudgetStatusResponse(**status)


@router.get("/alerts")
def get_cost_alerts(
    limit: int = 50,
    unresolved_only: bool = True,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Get recent cost alerts."""
    service = BudgetService(db)
    tenant_id = UUID(current_user["tenant_id"])

    alerts = service.get_recent_alerts(
        tenant_id=tenant_id,
        limit=limit,
        unresolved_only=unresolved_only,
    )

    return {
        "alerts": [
            {
                "id": str(alert.id),
                "alert_type": alert.alert_type,
                "severity": alert.severity,
                "title": alert.title,
                "message": alert.message,
                "current_spend_usd": alert.current_spend_usd,
                "budget_limit_usd": alert.budget_limit_usd,
                "is_resolved": alert.is_resolved,
                "created_at": alert.created_at.isoformat(),
            }
            for alert in alerts
        ],
        "total": len(alerts),
    }
