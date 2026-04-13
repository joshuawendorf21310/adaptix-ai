"""Alerting and observability API router."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Any
from uuid import UUID

from core_app.api.dependencies import get_db, get_current_user
from core_app.services.alerting_service import AlertingService

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


class CostSpikeDetectionRequest(BaseModel):
    """Request to detect cost spikes."""
    module: str | None = Field(None, description="Optional module filter")
    lookback_hours: int = Field(24, ge=1, le=168, description="Hours to look back for baseline")
    spike_threshold: float = Field(2.0, gt=1.0, description="Spike threshold multiplier")


class LatencyRegressionRequest(BaseModel):
    """Request to detect latency regression."""
    module: str | None = Field(None, description="Optional module filter")
    task_type: str | None = Field(None, description="Optional task type filter")
    lookback_hours: int = Field(24, ge=1, le=168, description="Hours to look back")
    regression_threshold: float = Field(1.5, gt=1.0, description="Regression threshold multiplier")


class QualityRegressionRequest(BaseModel):
    """Request to detect quality regression."""
    module: str | None = Field(None, description="Optional module filter")
    task_type: str | None = Field(None, description="Optional task type filter")
    lookback_hours: int = Field(24, ge=1, le=168, description="Hours to look back")
    error_rate_threshold: float = Field(0.1, ge=0.0, le=1.0, description="Error rate threshold")


class TaskFailureClusterRequest(BaseModel):
    """Request to detect task failure clustering."""
    lookback_hours: int = Field(1, ge=1, le=24, description="Hours to look back")
    cluster_threshold: int = Field(5, ge=2, description="Minimum failures for cluster")


class ResolveAlertRequest(BaseModel):
    """Request to resolve an alert."""
    resolution_notes: str | None = Field(None, description="Resolution notes")


@router.post("/detect/cost-spike")
def detect_cost_spike(
    request: CostSpikeDetectionRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Detect cost spikes compared to baseline."""
    service = AlertingService(db)
    tenant_id = UUID(current_user["tenant_id"])

    result = service.detect_cost_spike(
        tenant_id=tenant_id,
        module=request.module,
        lookback_hours=request.lookback_hours,
        spike_threshold=request.spike_threshold,
    )

    return result


@router.post("/detect/latency-regression")
def detect_latency_regression(
    request: LatencyRegressionRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Detect latency regression compared to baseline."""
    service = AlertingService(db)
    tenant_id = UUID(current_user["tenant_id"])

    result = service.detect_latency_regression(
        tenant_id=tenant_id,
        module=request.module,
        task_type=request.task_type,
        lookback_hours=request.lookback_hours,
        regression_threshold=request.regression_threshold,
    )

    return result


@router.post("/detect/quality-regression")
def detect_quality_regression(
    request: QualityRegressionRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Detect quality regression based on error rates."""
    service = AlertingService(db)
    tenant_id = UUID(current_user["tenant_id"])

    result = service.detect_quality_regression(
        tenant_id=tenant_id,
        module=request.module,
        task_type=request.task_type,
        lookback_hours=request.lookback_hours,
        error_rate_threshold=request.error_rate_threshold,
    )

    return result


@router.post("/detect/task-failure-cluster")
def detect_task_failure_cluster(
    request: TaskFailureClusterRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Detect clustering of task failures."""
    service = AlertingService(db)
    tenant_id = UUID(current_user["tenant_id"])

    result = service.detect_task_failure_clustering(
        tenant_id=tenant_id,
        lookback_hours=request.lookback_hours,
        cluster_threshold=request.cluster_threshold,
    )

    return result


@router.get("/active")
def get_active_alerts(
    severity: str | None = None,
    alert_type: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Get active (unresolved) alerts."""
    service = AlertingService(db)
    tenant_id = UUID(current_user["tenant_id"])

    alerts = service.get_active_alerts(
        tenant_id=tenant_id,
        severity=severity,
        alert_type=alert_type,
        limit=limit,
    )

    return {
        "alerts": [
            {
                "id": str(alert.id),
                "alert_type": alert.alert_type,
                "severity": alert.severity,
                "title": alert.title,
                "message": alert.message,
                "scope_type": alert.scope_type,
                "scope_value": alert.scope_value,
                "current_spend_usd": alert.current_spend_usd,
                "budget_limit_usd": alert.budget_limit_usd,
                "is_resolved": alert.is_resolved,
                "created_at": alert.created_at.isoformat(),
            }
            for alert in alerts
        ],
        "total": len(alerts),
    }


@router.post("/{alert_id}/resolve")
def resolve_alert(
    alert_id: UUID,
    request: ResolveAlertRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Resolve an alert."""
    service = AlertingService(db)
    user_id = UUID(current_user["user_id"])

    try:
        alert = service.resolve_alert(
            alert_id=alert_id,
            resolved_by=user_id,
            resolution_notes=request.resolution_notes,
        )

        return {
            "alert_id": str(alert.id),
            "is_resolved": alert.is_resolved,
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            "resolved_by": str(alert.resolved_by) if alert.resolved_by else None,
        }
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
